"""Optional multi-language symbol parsing via tree-sitter.

The core parses Python with the stdlib ``ast`` (zero dependencies). This module adds
symbol-level extraction — functions/classes and a within-file call graph — for JavaScript,
TypeScript, Go, Rust and Java, **only** when the optional ``[treesitter]`` extra is installed.
Everything degrades gracefully: with the extra absent, :func:`extract_symbols` returns ``None``
and the indexer falls back to file-level information for those languages.

tree-sitter's Python bindings have shipped two shapes over time — one where node fields are
*properties* (``node.type``, ``node.children``) and one where they are *methods*
(``node.kind()``, ``node.child(i)``). The small accessors below tolerate both, so the extra
keeps working across binding versions. The output (:class:`Symbol`) matches
:mod:`veridge.parse_python`, so the indexer treats every language through one code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache, lru_cache

LANG_BY_EXT: dict[str, str] = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".rs": "rust", ".java": "java",
}

_DEF_KINDS: dict[str, dict[str, str]] = {
    "javascript": {
        "function_declaration": "function", "generator_function_declaration": "function",
        "class_declaration": "class", "method_definition": "function",
    },
    "typescript": {
        "function_declaration": "function", "generator_function_declaration": "function",
        "class_declaration": "class", "abstract_class_declaration": "class",
        "interface_declaration": "class", "method_definition": "function",
    },
    "go": {"function_declaration": "function", "method_declaration": "function"},
    "rust": {
        "function_item": "function", "struct_item": "class",
        "enum_item": "class", "trait_item": "class",
    },
    "java": {
        "class_declaration": "class", "interface_declaration": "class",
        "enum_declaration": "class", "method_declaration": "function",
        "constructor_declaration": "function",
    },
}
_DEF_KINDS["tsx"] = _DEF_KINDS["typescript"]

_CALL_TYPES: dict[str, dict[str, str]] = {
    "javascript": {"call_expression": "function"},
    "typescript": {"call_expression": "function"},
    "tsx": {"call_expression": "function"},
    "go": {"call_expression": "function"},
    "rust": {"call_expression": "function", "macro_invocation": "macro"},
    "java": {"method_invocation": "name"},
}

_IDENT_TYPES = frozenset({
    "identifier", "property_identifier", "field_identifier", "type_identifier",
})


@dataclass
class Symbol:
    name: str
    qualname: str
    kind: str
    lineno: int
    calls: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def available() -> bool:
    """True if the optional tree-sitter extra is importable."""
    try:
        import tree_sitter_language_pack  # noqa: F401
        return True
    except Exception:
        return False


@cache
def _parser(lang: str):
    from tree_sitter_language_pack import get_parser
    return get_parser(lang)


# -- binding-shape-tolerant accessors (property vs method) ------------------
def _resolve(obj, name: str):
    v = getattr(obj, name, None)
    return v() if callable(v) else v


def _root(tree):
    r = tree.root_node
    return r() if callable(r) else r


def _ntype(node) -> str | None:
    t = getattr(node, "type", None)
    if isinstance(t, str):
        return t
    k = _resolve(node, "kind")
    return k if isinstance(k, str) else None


def _children(node) -> list:
    ch = getattr(node, "children", None)
    if isinstance(ch, (list, tuple)):
        return list(ch)
    cnt = _resolve(node, "child_count") or 0
    return [node.child(i) for i in range(cnt)]


def _field_child(node, field_name: str):
    f = getattr(node, "child_by_field_name", None)
    if f is None:
        return None
    try:
        return f(field_name)
    except Exception:
        return None


def _line(node) -> int:
    for attr in ("start_point", "start_position"):
        p = getattr(node, attr, None)
        if p is None:
            continue
        p = p() if callable(p) else p
        row = getattr(p, "row", None)
        if row is None and hasattr(p, "__getitem__"):
            row = p[0]
        if row is not None:
            return int(row) + 1
    return 1


def _text(node, data: bytes) -> str:
    sb, eb = _resolve(node, "start_byte"), _resolve(node, "end_byte")
    return data[sb:eb].decode("utf-8", "ignore")


def _name_of(node, data: bytes) -> str | None:
    nm = _field_child(node, "name")
    return _text(nm, data) if nm is not None else None


def _last_ident(node, data: bytes) -> str | None:
    """The last identifier-like leaf under ``node`` (the bare callee name of a call)."""
    order: list = []

    def collect(n):
        if _ntype(n) in _IDENT_TYPES and not _children(n):
            order.append(n)
        for c in _children(n):
            collect(c)

    collect(node)
    return _text(order[-1], data) if order else None


def _callee_name(node, data: bytes, field_name: str) -> str | None:
    return _last_ident(_field_child(node, field_name) or node, data)


def _walk(node, lang: str, data: bytes, stack: list[Symbol], out: list[Symbol]) -> None:
    defs = _DEF_KINDS[lang]
    calls = _CALL_TYPES[lang]
    t = _ntype(node)
    pushed = False
    if t in defs:
        name = _name_of(node, data)
        if name:
            qual = f"{stack[-1].qualname}.{name}" if stack else name
            sym = Symbol(name, qual, defs[t], _line(node), [])
            out.append(sym)
            stack.append(sym)
            pushed = True
    elif t in calls and stack:
        callee = _callee_name(node, data, calls[t])
        if callee and callee not in stack[-1].calls:
            stack[-1].calls.append(callee)
    for ch in _children(node):
        _walk(ch, lang, data, stack, out)
    if pushed:
        stack.pop()


def extract_symbols(ext: str, source: str) -> list[Symbol] | None:
    """Return the symbols defined in ``source`` for the language of ``ext``.

    ``None`` means "not handled here" — the extra is missing, the language is unsupported, or
    parsing failed — so the caller falls back cleanly.
    """
    lang = LANG_BY_EXT.get(ext)
    if lang is None or not available():
        return None
    try:
        parser = _parser(lang)
        data = source.encode("utf-8", "ignore")
        try:
            tree = parser.parse(source)          # method-style bindings want str
        except TypeError:
            tree = parser.parse(data)            # property-style bindings want bytes
        out: list[Symbol] = []
        _walk(_root(tree), lang, data, [], out)
        return out
    except Exception:
        return None
