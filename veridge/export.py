"""Export the graph to interchange formats, so anything can build on it.

Veridge's own ``graph.json`` (``native``) is the canonical, versioned contract. For
consumption by other tools this module also emits **JSON Graph Format** (``jgf`` — a widely
understood JSON shape) and **Graphviz DOT** (``dot`` — for rendering). Betting on a generic
format rather than one downstream tool's schema keeps the integration durable: an agent, a
notebook, a visualiser or an LLM-comprehension tool can all read the same export.
"""

from __future__ import annotations

import json

from veridge.model import SCHEMA_VERSION, Graph, Node

FORMATS = ("native", "jgf", "dot")


def _node_metadata(n: Node) -> dict:
    md: dict = {"kind": n.kind.value}
    if n.category:
        md["category"] = n.category.value
    if n.path:
        md["path"] = n.path
    if n.description:
        md["description"] = n.description
    md.update(n.meta)
    return md


def to_jgf(graph: Graph) -> dict:
    """Return the graph as JSON Graph Format (a single directed graph)."""
    return {
        "graph": {
            "directed": True,
            "label": graph.project,
            "metadata": {"generator": "veridge", "schema_version": SCHEMA_VERSION},
            "nodes": {
                n.id: {"label": n.label, "metadata": _node_metadata(n)}
                for n in sorted(graph.nodes.values(), key=lambda n: n.id)
            },
            "edges": [
                {"source": e.source, "target": e.target, "relation": e.type.value,
                 **({"metadata": e.meta} if e.meta else {})}
                for e in sorted(graph.edges, key=lambda e: (e.source, e.target, e.type.value))
            ],
        }
    }


def _dot_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_dot(graph: Graph) -> str:
    """Return the graph as a Graphviz DOT digraph (nodes coloured by kind)."""
    from veridge.model import KIND_COLORS
    lines = [f"digraph {_dot_quote(graph.project or 'project')} {{", "  rankdir=LR;",
             "  node [shape=ellipse, style=filled, fontsize=10];"]
    for n in sorted(graph.nodes.values(), key=lambda n: n.id):
        color = KIND_COLORS.get(n.kind, "#9aa4b2")
        lines.append(f"  {_dot_quote(n.id)} [label={_dot_quote(n.label)}, "
                     f"fillcolor={_dot_quote(color)}, fontcolor=white];")
    for e in sorted(graph.edges, key=lambda e: (e.source, e.target, e.type.value)):
        lines.append(f"  {_dot_quote(e.source)} -> {_dot_quote(e.target)} "
                     f"[label={_dot_quote(e.type.value)}];")
    lines.append("}")
    return "\n".join(lines)


def export(graph: Graph, fmt: str) -> str:
    """Serialise ``graph`` to ``fmt`` (one of :data:`FORMATS`) as text."""
    if fmt == "native":
        return graph.to_json()
    if fmt == "jgf":
        return json.dumps(to_jgf(graph), ensure_ascii=False, indent=2)
    if fmt == "dot":
        return to_dot(graph)
    raise ValueError(f"unknown export format {fmt!r}; choose from {', '.join(FORMATS)}")
