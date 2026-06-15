"""Deterministic blast-radius over the dependency graph — no LLM, no cost.

"If I change X, what is affected?" is *reverse reachability* over the typed edges we already
build: a node's **dependents** are everything that transitively points at it. The mirror
question, "what does X rely on?", is forward reachability (its **dependencies**).

Granularity is bridged automatically: a file seed is lifted to the symbols it defines and a
symbol seed to its file, so ``impact src/util.py`` and ``impact greet`` both reach symbol-level
callers *and* file-level importers. Propagation follows ``imports``/``calls``/``references``/
``defines``; membership and history edges (``belongs_to``/``touches``/``mentions``) don't carry
change impact and are ignored.
"""

from __future__ import annotations

from veridge.model import EdgeType, Graph, Kind

# Edge types along which a change propagates.
PROPAGATING: frozenset[EdgeType] = frozenset({
    EdgeType.IMPORTS, EdgeType.CALLS, EdgeType.REFERENCES, EdgeType.DEFINES,
})


def expand_seed(graph: Graph, seed: str) -> set[str]:
    """Lift a seed across granularity: file -> its symbols, symbol -> its file."""
    if seed not in graph.nodes:
        return set()
    out = {seed}
    n = graph.nodes[seed]
    if n.kind is Kind.FILE:
        for e in graph.out_edges(seed):
            if e.type is EdgeType.DEFINES:
                out.add(e.target)
    elif n.kind is Kind.SYMBOL:
        for e in graph.in_edges(seed):
            if e.type is EdgeType.DEFINES:
                out.add(e.source)
    return out


def _reach(graph: Graph, seeds: set[str], *, reverse: bool, hops: int | None) -> dict[str, int]:
    """BFS distances from ``seeds``; ``reverse`` follows in-edges (dependents)."""
    dist: dict[str, int] = {s: 0 for s in seeds if s in graph.nodes}
    frontier = set(dist)
    d = 0
    while frontier and (hops is None or d < hops):
        d += 1
        nxt: set[str] = set()
        for nid in frontier:
            edges = graph.in_edges(nid) if reverse else graph.out_edges(nid)
            for e in edges:
                if e.type not in PROPAGATING:
                    continue
                other = e.source if reverse else e.target
                if other not in dist:
                    dist[other] = d
                    nxt.add(other)
        frontier = nxt
    return dist


def dependents(graph: Graph, seeds: set[str], *, hops: int | None = None) -> dict[str, int]:
    """Nodes affected by a change to ``seeds`` (reverse reachability), id -> distance."""
    return _reach(graph, seeds, reverse=True, hops=hops)


def dependencies(graph: Graph, seeds: set[str], *, hops: int | None = None) -> dict[str, int]:
    """Nodes ``seeds`` rely on (forward reachability), id -> distance."""
    return _reach(graph, seeds, reverse=False, hops=hops)
