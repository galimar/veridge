"""Build the unified project graph: files, symbols, areas, decisions, sessions.

Edges produced:

* ``defines``    file -> symbol it declares (Python; other langs via the optional extra)
* ``imports``    code -> code at the file level (Python via ``ast``, JS/TS best-effort)
* ``calls``      symbol -> symbol, resolved within the project (a real call graph)
* ``references`` doc -> file (markdown link / wikilink / path-in-prose)
* ``mentions``   doc -> decision
* ``belongs_to`` file -> area
* ``touches``    session(commit) -> file

Reference resolution is conservative: a reference is flagged *broken* only when an
intentional link points inside the project and cannot be found, so the gate stays honest.
The project is never modified.
"""

from __future__ import annotations

import os
import posixpath
import re
from collections.abc import Iterator
from pathlib import Path

from veridge import laravel, treesitter
from veridge.aliases import load_aliases
from veridge.classify import classify
from veridge.model import Edge, EdgeType, Graph, Kind, Node
from veridge.parse_docs import extract_decisions, extract_references
from veridge.parse_python import PyImport, parse_python
from veridge.walk import iter_files

AREA_ROOT = "(root)"
_MAX_READ_BYTES = 5_000_000
# Files whose imports are scanned with the JS regex (Vue's <script> imports count too).
_JS_EXTS = {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}
_JS_IMPORT_EXTS = _JS_EXTS | {".vue"}
# Files we extract symbols from via tree-sitter (only when the extra is installed); incl. .vue.
_TS_EXTS = treesitter.SYMBOL_EXTS
_DOC_REF_EXTS = {".md", ".markdown", ".rst", ".txt", ".html", ".htm", ".adoc"}
_JS_RESOLVE_ORDER = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue",
                     "/index.ts", "/index.js", "/index.vue")
# Capture any specifier; the resolver decides (relative -> path, alias -> tsconfig, else drop).
_JS_IMPORT_RE = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*|export\s[^'"]*?from\s*|require\(\s*)['"]([^'"]+)['"]"""
)


def _ext(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def _top_area(rel: str) -> str:
    return rel.split("/", 1)[0] if "/" in rel else AREA_ROOT


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_READ_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def _python_module_map(py_files: list[str]) -> dict[str, str]:
    """Map dotted module/package name -> file, packages winning over same-named modules."""
    modules: dict[str, str] = {}
    for rel in py_files:
        dotted = rel[:-3].replace("/", ".")           # strip ".py", turn the path into a name
        if dotted == "__init__":
            continue                                  # a root __init__ names no module
        if dotted.endswith(".__init__"):
            modules[dotted[: -len(".__init__")]] = rel   # package: set unconditionally (wins)
        else:
            modules.setdefault(dotted, rel)           # module: never shadow a package
    return modules


def _py_candidates(imp: PyImport, from_rel: str) -> Iterator[str]:
    """Yield the dotted names an import statement could resolve to (absolute or relative)."""
    package = from_rel[:-3].split("/")[:-1]           # package path of the importing module
    if imp.level == 0:
        if imp.module:
            yield imp.module
            for name in imp.names:
                yield f"{imp.module}.{name}"
        return
    keep = len(package) - (imp.level - 1)
    if keep < 0:
        return                                        # relative import climbs above the root
    prefix = package[:keep] + (imp.module.split(".") if imp.module else [])
    if imp.module:
        yield ".".join(prefix)
    for name in imp.names:
        yield ".".join(prefix + [name])


def _resolve_py(imp: PyImport, from_rel: str, module_map: dict[str, str]) -> list[str]:
    """Resolve one import to the internal files it targets (deduped, never itself)."""
    out: list[str] = []
    for cand in _py_candidates(imp, from_rel):
        target = module_map.get(cand)
        if target and target != from_rel and target not in out:
            out.append(target)
    return out


def _try_js_suffixes(base: str, from_rel: str, node_ids: set[str]) -> str | None:
    for suffix in _JS_RESOLVE_ORDER:
        candidate = base + suffix
        if candidate != from_rel and candidate in node_ids:
            return candidate
    return None


def _resolve_js(spec: str, from_rel: str, node_ids: set[str],
                aliases: list[tuple[str, str]]) -> str | None:
    """Resolve a JS/TS/Vue import specifier — relative (``./``) or an alias (``@/…``)."""
    if spec.startswith("."):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), spec))
        return _try_js_suffixes(base, from_rel, node_ids)
    for prefix, target in aliases:                       # longest prefix first
        if spec.startswith(prefix):
            base = posixpath.normpath(f"{target}/{spec[len(prefix):]}")
            hit = _try_js_suffixes(base, from_rel, node_ids)
            if hit:
                return hit
    return None


def _is_external(target: str) -> bool:
    """True for URLs, UNC paths (``//host``), and Windows drive paths (``C:/...``)."""
    return (
        "://" in target
        or target.startswith("//")
        or (len(target) >= 2 and target[1] == ":" and target[0].isalpha())
    )


def _unique_hit(index: dict[str, list[str]], key: str, exclude: str) -> str | None:
    hits = [i for i in index.get(key, ()) if i != exclude]
    return hits[0] if len(hits) == 1 else None


def _resolve_ref(
    target: str, kind: str, from_rel: str, node_ids: set[str],
    basename_index: dict[str, list[str]], stem_index: dict[str, list[str]],
) -> tuple[str | None, bool]:
    """Resolve a documentation reference to a file id. Returns ``(resolved_or_None, is_broken)``."""
    if not target:
        return None, False
    as_relative = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), target))
    as_rooted = posixpath.normpath(target.lstrip("/"))
    for candidate in (as_relative, as_rooted):
        if candidate in node_ids:
            return (None if candidate == from_rel else candidate), False

    base = target.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    for index, key in ((basename_index, base), (stem_index, stem)):
        hit = _unique_hit(index, key, from_rel)
        if hit:
            return hit, False

    # Unresolved: a bare prose path, an external/up-and-out target, or a bare concept wikilink
    # is just noise; only an intentional in-project link/wikilink that misses is truly broken.
    if kind == "path" or _is_external(target):
        return None, False
    if as_relative.startswith("../") or as_rooted.startswith("../"):
        return None, False
    if kind == "wikilink" and "/" not in target and "." not in base:
        return None, False
    return None, True


def _add_symbols(g: Graph, rel: str, symbols, sym_index: dict[str, list[str]],
                 file_syms: dict[str, list[str]],
                 pending_calls: list[tuple[str, str, list[str]]]) -> None:
    """Add symbol nodes + ``defines`` edges, and index names/calls for the call graph.

    ``symbols`` items only need ``.name/.qualname/.kind/.lineno/.calls`` — satisfied by both
    :class:`veridge.parse_python.PySymbol` and :class:`veridge.treesitter.Symbol`, so every
    language flows through this one path.
    """
    for s in symbols:
        sid = f"{rel}#{s.qualname}"
        g.add_node(Node(id=sid, kind=Kind.SYMBOL, label=s.qualname, path=rel,
                        meta={"line": s.lineno, "symbol": s.kind}))
        g.add_edge(Edge(rel, sid, EdgeType.DEFINES))
        sym_index.setdefault(s.name, []).append(sid)
        file_syms.setdefault(rel, []).append(sid)
        if s.calls:
            pending_calls.append((sid, rel, s.calls))


def _wire_laravel(g: Graph, laravel_files: list[tuple[str, str]],
                  sym_index: dict[str, list[str]]) -> None:
    """Add `references` edges for Laravel route->controller and event->listener wiring."""
    def class_sym(name: str) -> str | None:
        ids = [i for i in sym_index.get(name, ())
               if g.nodes.get(i) is not None and g.nodes[i].meta.get("symbol") == "class"]
        return ids[0] if len(ids) == 1 else None

    for rel, text in laravel_files:
        if laravel.is_route_file(rel):
            for name in laravel.route_class_refs(text):
                tgt = class_sym(name)
                if tgt:
                    g.add_edge(Edge(rel, tgt, EdgeType.REFERENCES))
        elif laravel.is_event_provider(rel):
            for event, listeners in laravel.event_listener_pairs(text):
                ev = class_sym(event)
                if ev is None:
                    continue
                for lname in listeners:
                    ln = class_sym(lname)
                    if ln and ln != ev:
                        # listener depends on (handles) the event -> impact(event) finds it
                        g.add_edge(Edge(ln, ev, EdgeType.REFERENCES))


def build_graph(root: str | os.PathLike[str], *, project: str | None = None,
                _rels: list[str] | None = None, sessions: bool = True) -> Graph:
    """Index the project at ``root`` and return its graph. Never modifies the project."""
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        raise NotADirectoryError(f"not a directory: {root_p}")
    rels = _rels if _rels is not None else iter_files(root_p)
    g = Graph(project=project or root_p.name)

    # 1. File nodes + areas.
    areas: set[str] = set()
    for rel in rels:
        node = Node(id=rel, kind=Kind.FILE, label=rel.rsplit("/", 1)[-1],
                    path=rel, category=classify(rel))
        try:
            node.meta["size"] = (root_p / rel).stat().st_size
        except OSError:
            pass
        g.add_node(node)
        areas.add(_top_area(rel))
    for area in sorted(areas):
        g.add_node(Node(id=f"area:{area}", kind=Kind.AREA, label=area))
    for rel in rels:
        g.add_edge(Edge(rel, f"area:{_top_area(rel)}", EdgeType.BELONGS_TO))

    # 2. Resolution indexes.
    node_ids = set(g.nodes.keys())
    basename_index: dict[str, list[str]] = {}
    stem_index: dict[str, list[str]] = {}
    for rel in rels:
        base = rel.rsplit("/", 1)[-1]
        basename_index.setdefault(base, []).append(rel)
        stem = base.rsplit(".", 1)[0] if "." in base else base
        stem_index.setdefault(stem, []).append(rel)
    py_files = [r for r in rels if _ext(r) == ".py"]
    module_map = _python_module_map(py_files)
    alias_rules = load_aliases(root_p)            # JS/TS/Vue import aliases (@/, ~, tsconfig paths)

    # 3. Parse contents. Only code and docs are read; data/config/binaries are never opened.
    #    `pending_calls`: (owner_symbol_id, file_rel, [called names]) resolved in pass 4.
    sym_index: dict[str, list[str]] = {}          # simple name -> [symbol ids]
    file_syms: dict[str, list[str]] = {}          # file rel -> [symbol ids in it]
    pending_calls: list[tuple[str, str, list[str]]] = []
    laravel_files: list[tuple[str, str]] = []     # (rel, text) for route / event-provider files
    decisions: set[str] = set()

    for rel in rels:
        ext = _ext(rel)
        is_py = ext == ".py"
        is_js_imports = ext in _JS_IMPORT_EXTS          # JS/TS/Vue: scan imports with the regex
        is_ts = ext in _TS_EXTS and treesitter.available()
        is_doc = ext in _DOC_REF_EXTS
        if not (is_py or is_js_imports or is_ts or is_doc):
            continue
        text = _read_text(root_p / rel)
        if text is None:
            continue
        if ext == ".php" and laravel.is_wiring_file(rel):
            laravel_files.append((rel, text))      # resolved in pass 5, once all symbols exist
        if is_py:
            mod = parse_python(text)
            for imp in mod.imports:
                for tgt in _resolve_py(imp, rel, module_map):
                    g.add_edge(Edge(rel, tgt, EdgeType.IMPORTS))
            _add_symbols(g, rel, mod.symbols, sym_index, file_syms, pending_calls)
        else:
            if is_ts:  # symbols + call graph for JS/TS/Go/Rust/Java/PHP, and Vue <script>
                syms = treesitter.extract_symbols(ext, text)
                if syms:
                    _add_symbols(g, rel, syms, sym_index, file_syms, pending_calls)
            if is_js_imports:  # relative + aliased imports (works with or without the extra)
                for m in _JS_IMPORT_RE.finditer(text):
                    tgt = _resolve_js(m.group(1), rel, node_ids, alias_rules)
                    if tgt:
                        g.add_edge(Edge(rel, tgt, EdgeType.IMPORTS))
        if is_doc:
            broken: list[str] = []
            for target, kind in extract_references(text):
                resolved, is_broken = _resolve_ref(
                    target, kind, rel, node_ids, basename_index, stem_index)
                if resolved:
                    g.add_edge(Edge(rel, resolved, EdgeType.REFERENCES))
                elif is_broken:
                    broken.append(target)
            if broken:
                g.nodes[rel].meta["broken_refs"] = broken
            for did in extract_decisions(text):
                nid = f"decision:{did}"
                if nid not in g.nodes:
                    g.add_node(Node(id=nid, kind=Kind.DECISION, label=did,
                                    description=f"decision {did}"))
                    decisions.add(did)
                g.add_edge(Edge(rel, nid, EdgeType.MENTIONS))

    # 4. Resolve symbol calls to a real call graph (same-file first, then project-unique).
    for owner, rel, calls in pending_calls:
        local = {sid for sid in file_syms.get(rel, [])}
        for name in calls:
            cands = sym_index.get(name, [])
            target = next((c for c in cands if c in local), None)
            if target is None and len(cands) == 1:
                target = cands[0]
            if target and target != owner:
                g.add_edge(Edge(owner, target, EdgeType.CALLS))

    # 4b. Laravel wiring (best-effort): routes -> controllers, events -> listeners. The links are
    #     `references` edges to the resolved class symbol, so impact/focus follow them too.
    _wire_laravel(g, laravel_files, sym_index)

    # 5. Sessions from git (optional, best-effort, read-only).
    if sessions:
        from veridge.sessions import add_sessions
        add_sessions(g, root_p)

    # 6. Descriptions (after edges, so inbound counts are available).
    _describe(g)
    return g


def _describe(g: Graph) -> None:
    for node in g.nodes.values():
        if node.kind is Kind.AREA:
            node.description = f"area '{node.label}'"
            continue
        inbound = len(g.in_edges(node.id))
        if node.kind is Kind.SYMBOL:
            node.description = f"{node.meta.get('symbol', 'symbol')} in {node.path}"
        elif node.kind is Kind.FILE:
            cat = node.category.value if node.category else "file"
            area = _top_area(node.path) if node.path else AREA_ROOT
            where = "root" if area == AREA_ROOT else f"area '{area}'"
            tail = f" · {inbound} inbound" if inbound else ""
            node.description = f"{cat} · {where}{tail}"
        elif node.kind is Kind.DECISION:
            node.description = f"decision · {inbound} mentions"
