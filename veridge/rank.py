"""Relevance ranking over the graph — pure-Python PageRank, no numpy.

Two modes share one implementation:

* **Global PageRank** (uniform restart) — "what matters in this project overall", the
  default ordering for the project digest and the most-connected list.
* **Personalised PageRank / random-walk-with-restart** (restart biased to a set of *seed*
  nodes) — "what matters *for this task*". Restarting the walk on the seeds spreads relevance
  to their structural neighbourhood, which is exactly the context an assistant needs when it
  starts from a file, a symbol, or a free-text query. This is what makes ``veridge focus``
  task-aware instead of returning a fixed digest.

Edges are treated as undirected and weighted by type (see ``EDGE_WEIGHT``) so importance
flows both ways: a file is important if it imports, and if it is imported by, important code.
"""

from __future__ import annotations

from veridge.model import Graph


def pagerank(
    graph: Graph,
    *,
    seeds: dict[str, float] | None = None,
    damping: float = 0.85,
    iters: int = 60,
    tol: float = 1e-9,
) -> dict[str, float]:
    """Return ``{node_id: score}`` (scores sum to ~1).

    ``seeds`` biases the restart distribution toward those nodes (personalised PageRank);
    ``None`` uses a uniform restart (classic PageRank). Unknown seed ids are ignored.
    """
    adj = graph.undirected_weights()
    nodes = list(graph.nodes.keys())
    n = len(nodes)
    if n == 0:
        return {}

    # Restart vector.
    if seeds:
        kept = {k: max(0.0, v) for k, v in seeds.items() if k in graph.nodes}
        total = sum(kept.values())
        if total <= 0:
            restart = {k: 1.0 / n for k in nodes}
        else:
            restart = {k: 0.0 for k in nodes}
            for k, v in kept.items():
                restart[k] = v / total
    else:
        restart = {k: 1.0 / n for k in nodes}

    # Pre-compute outgoing weight sums (undirected degree-weight).
    wsum = {k: sum(adj.get(k, {}).values()) for k in nodes}
    score = dict(restart)

    for _ in range(max(1, iters)):
        nxt = {k: (1.0 - damping) * restart[k] for k in nodes}
        dangling = 0.0
        for k in nodes:
            s = score[k]
            w = wsum[k]
            if w <= 0:
                dangling += s  # isolated node leaks its mass to the restart distribution
                continue
            share = damping * s
            for nb, wt in adj[k].items():
                nxt[nb] += share * (wt / w)
        if dangling:
            for k in nodes:
                nxt[k] += damping * dangling * restart[k]
        delta = sum(abs(nxt[k] - score[k]) for k in nodes)
        score = nxt
        if delta < tol:
            break
    return score


def top_ranked(scores: dict[str, float], graph: Graph, *, kind=None, limit: int = 10):
    """Return ``[(id, score)]`` sorted by score desc, id asc; optional kind filter."""
    items = [
        (nid, sc) for nid, sc in scores.items()
        if nid in graph.nodes and (kind is None or graph.nodes[nid].kind is kind)
    ]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return items[:limit]
