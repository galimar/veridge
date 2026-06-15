"""Token budgeting: turn a ranking into the *most* context that fits a token ceiling.

The point of Veridge is to hand an assistant the **minimal relevant slice** of a project,
not the whole thing. Given a ranked list of node ids and a token budget, we greedily admit
the highest-ranked nodes whose compact rows still fit. Token cost uses the standard ~4
chars/token heuristic on the *compact row* an assistant would actually read — ids, kinds,
sizes and edge counts, never file contents.
"""

from __future__ import annotations

import json
from typing import Any

from veridge.model import Graph, Kind


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def node_row(graph: Graph, nid: str) -> dict[str, Any]:
    """A compact, contents-free row for one node (what an assistant reads)."""
    n = graph.nodes[nid]
    row: dict[str, Any] = {"id": n.id, "kind": n.kind.value}
    if n.category:
        row["cat"] = n.category.value
    if n.kind is Kind.FILE:
        row["size"] = int(n.meta.get("size", 0))
    if n.kind is Kind.SYMBOL and n.meta.get("line"):
        row["line"] = n.meta["line"]
    row["deg"] = graph.degree(nid)
    return row


def _row_cost(row: dict[str, Any]) -> int:
    # Cost the row as the JSON the assistant actually receives (over the CLI's --json or MCP),
    # not a looser key=value form — so a "1500-token budget" reflects real consumption.
    return estimate_tokens(json.dumps(row, ensure_ascii=False))


def select_within_budget(
    graph: Graph, ranked_ids: list[str], budget_tokens: int,
) -> tuple[list[dict[str, Any]], int]:
    """Admit ranked nodes (best first) until the token budget is exhausted.

    Returns ``(rows, used_tokens)``. Always returns at least the single best node, even if it
    alone exceeds the budget, so a query never comes back empty.
    """
    rows: list[dict[str, Any]] = []
    used = 0
    for nid in ranked_ids:
        if nid not in graph.nodes:
            continue
        row = node_row(graph, nid)
        cost = _row_cost(row)
        if rows and used + cost > budget_tokens:
            break
        rows.append(row)
        used += cost
    return rows, used
