"""Symbol-level Python parsing with the standard-library ``ast`` (no dependency).

Returns, for one source file: its imports, the symbols it defines (top-level functions and
classes, plus one level of methods), and — per symbol — the bare names it *calls*. The
indexer resolves those names to real symbol nodes across the project; here we only extract.

This is the core's built-in language. Other languages plug in through the same shape via the
optional ``[treesitter]`` extra (see :mod:`veridge.parsers`).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PyImport:
    level: int
    module: str | None
    names: tuple[str, ...]


@dataclass
class PySymbol:
    name: str           # simple name, e.g. "build_graph"
    qualname: str       # "Class.method" for methods, else == name
    kind: str           # "function" | "class"
    lineno: int
    calls: list[str] = field(default_factory=list)  # bare names this symbol invokes


@dataclass
class PyModule:
    imports: list[PyImport] = field(default_factory=list)
    symbols: list[PySymbol] = field(default_factory=list)


def _callee_name(call: ast.Call) -> str | None:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _called_names(node: ast.AST, *, skip: frozenset = frozenset()) -> list[str]:
    """Bare callee names inside ``node``, in first-seen order.

    Subtrees in ``skip`` are not descended into — used so a class symbol collects only its
    *own* calls, not those inside its methods (which are separate symbols). That avoids the
    same call being counted on both the class and the method.
    """
    out: list[str] = []
    seen: set[str] = set()

    def visit(n: ast.AST) -> None:
        for child in ast.iter_child_nodes(n):
            if child in skip:
                continue
            if isinstance(child, ast.Call):
                name = _callee_name(child)
                if name and name not in seen:
                    seen.add(name)
                    out.append(name)
            visit(child)

    visit(node)
    return out


def parse_python(source: str) -> PyModule:
    """Parse Python source into a :class:`PyModule`. Returns empty on syntax error."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return PyModule()

    mod = PyModule()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod.imports.append(PyImport(0, alias.name, ()))
        elif isinstance(node, ast.ImportFrom):
            names = tuple(a.name for a in node.names)
            mod.imports.append(PyImport(node.level or 0, node.module, names))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mod.symbols.append(PySymbol(node.name, node.name, "function",
                                        node.lineno, _called_names(node)))
        elif isinstance(node, ast.ClassDef):
            methods = [b for b in node.body
                       if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))]
            mod.symbols.append(PySymbol(
                node.name, node.name, "class", node.lineno,
                _called_names(node, skip=frozenset(methods))))
            for item in methods:
                mod.symbols.append(PySymbol(
                    item.name, f"{node.name}.{item.name}", "function",
                    item.lineno, _called_names(item)))
    return mod
