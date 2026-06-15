"""Heuristic architectural layers — deterministic, no LLM.

Layers are inferred deterministically from path segments, file category and filename
conventions — no LLM. The rules are intentionally simple and tunable; they
group files into a handful of familiar buckets so ``veridge map`` can show a project's shape at a
glance. When nothing matches, a code file falls back to ``core``.
"""

from __future__ import annotations

from veridge.model import Category, Graph, Kind, Node

# Display order (foundational/entry first), used by callers that render layers.
LAYER_ORDER = ["entrypoint", "api", "service", "core", "data", "ui", "util",
               "tests", "config", "docs", "other"]

_KEYWORDS: list[tuple[str, frozenset[str]]] = [
    ("entrypoint", frozenset({"main", "cli", "app", "server", "cmd", "__main__", "manage"})),
    ("api", frozenset({"api", "route", "routes", "controller", "controllers", "endpoint",
                       "endpoints", "handler", "handlers", "rest", "graphql", "http", "web"})),
    ("ui", frozenset({"ui", "component", "components", "page", "pages", "view", "views",
                      "widget", "widgets", "frontend", "template", "templates", "styles"})),
    ("data", frozenset({"model", "models", "schema", "schemas", "entity", "entities",
                        "repository", "repositories", "dao", "store", "stores", "db",
                        "database", "migration", "migrations", "orm"})),
    ("service", frozenset({"service", "services", "usecase", "usecases", "domain", "logic",
                           "manager", "managers", "provider", "providers", "worker", "workers"})),
    ("util", frozenset({"util", "utils", "helper", "helpers", "common", "lib", "libs",
                        "shared", "tool", "tools", "support"})),
]


def layer_of(node: Node) -> str:
    """Return the architectural layer for a node (files only; others -> 'other')."""
    if node.kind is not Kind.FILE or not node.path:
        return "other"
    parts = [p.lower() for p in node.path.split("/")]
    name = parts[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name

    if "test" in parts or "tests" in parts or stem.startswith("test_") or stem.endswith("_test"):
        return "tests"
    if node.category is Category.DATA:
        return "data"
    if node.category is Category.CONFIG:
        return "config"
    if node.category in (Category.DOC, Category.STRUCTURE, Category.MEMORY):
        return "docs"
    # Code files: first keyword hit wins, scanning the path segments and the stem.
    tokens = set(parts) | {stem} | set(stem.replace("-", "_").split("_"))
    for layer, kws in _KEYWORDS:
        if tokens & kws:
            return layer
    return "core"


def layer_summary(graph: Graph) -> list[dict[str, int | str]]:
    """Per-layer file counts and total size, ordered by :data:`LAYER_ORDER`."""
    acc: dict[str, dict[str, int]] = {}
    for n in graph.nodes.values():
        if n.kind is not Kind.FILE:
            continue
        lay = layer_of(n)
        e = acc.setdefault(lay, {"files": 0, "size": 0})
        e["files"] += 1
        e["size"] += int(n.meta.get("size", 0))
    rank = {lay: i for i, lay in enumerate(LAYER_ORDER)}
    rows = [{"layer": lay, "files": v["files"], "size": v["size"]} for lay, v in acc.items()]
    rows.sort(key=lambda r: (rank.get(r["layer"], len(LAYER_ORDER)), r["layer"]))
    return rows
