"""Optional MCP server: exposes Veridge's ranked, budgeted queries to MCP-aware assistants.

Optional extra so the core stays dependency-free:

    pip install veridge[mcp]
    veridge-mcp [PROJECT_PATH]      # defaults to the current directory

Read-only on your sources. The headline tool is ``focus`` — give it a task and a token
budget, get back the minimal relevant subgraph.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from veridge import query, store
from veridge.freshness import build_manifest, evaluate, index
from veridge.model import Graph

try:  # pragma: no cover - import guard
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

_NO_MCP = "The MCP server needs the optional 'mcp' extra: pip install veridge[mcp]"


def _graph(project: str) -> Graph:
    return store.load_graph(project) or index(project)[0]


def build_server(project: str):
    if FastMCP is None:  # pragma: no cover
        raise ImportError(_NO_MCP)
    server = FastMCP("veridge")

    @server.tool()
    def project_map() -> dict[str, Any]:
        """Compact, PageRank-ranked project digest. Cheap to load first."""
        return query.project_map(_graph(project))

    @server.tool()
    def focus(task: str, budget_tokens: int = 1500) -> dict[str, Any]:
        """Minimal relevant subgraph for a task/file/symbol, within a token budget."""
        return query.focus(_graph(project), task, budget_tokens=budget_tokens)

    @server.tool()
    def impact(seed: str, budget_tokens: int = 1500, dependencies: bool = False,
               hops: int | None = None) -> dict[str, Any]:
        """Blast-radius of a change to a file/symbol: the affected subgraph, ranked & budgeted.

        Set ``dependencies=True`` to invert (what the seed relies on instead of what relies
        on it)."""
        direction = "dependencies" if dependencies else "dependents"
        return query.impact(_graph(project), seed, budget_tokens=budget_tokens,
                            hops=hops, direction=direction)

    @server.tool()
    def find(text: str) -> list[dict[str, Any]]:
        """Find nodes whose name or path contains ``text`` (case-insensitive)."""
        return query.find(_graph(project), text)

    @server.tool()
    def neighbors(node_id: str) -> dict[str, Any]:
        """A node and its incoming/outgoing connections."""
        res = query.neighbors(_graph(project), node_id)
        return res if res is not None else {"error": "node not found", "id": node_id}

    @server.tool()
    def why(a: str, b: str) -> dict[str, Any]:
        """Shortest typed path between two nodes — how A connects to B."""
        return query.why(_graph(project), a, b)

    @server.tool()
    def tour(budget_tokens: int = 2000) -> dict[str, Any]:
        """A dependency-ordered reading tour of the project's most important files."""
        return query.tour(_graph(project), budget_tokens=budget_tokens)

    @server.tool()
    def health() -> dict[str, Any]:
        """Anti-drift status: broken references, stale files vs the last build, orphans."""
        g = store.load_graph(project)
        old = store.load_manifest(project)
        if g is None or old is None:
            return {"status": "no-baseline", "hint": "run 'veridge build' first"}
        rep = evaluate(g, old, build_manifest(project))
        return {"ok": rep.ok, "broken": rep.broken, "stale": rep.stale,
                "orphans": len(rep.orphans)}

    return server


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    project = args[0] if args else os.getcwd()
    if FastMCP is None:
        print(_NO_MCP, file=sys.stderr)
        return 2
    build_server(project).run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
