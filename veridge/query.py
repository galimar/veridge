"""The query layer an assistant talks to. Compact, ranked, budgeted — never file contents.

* :func:`project_map` — the cheap digest to load when work starts (areas, tallies, the
  globally most-important nodes by PageRank, drift counts).
* :func:`find` — locate nodes by name/path substring.
* :func:`neighbors` — a node and its typed connections.
* :func:`focus` — **the signature query**: given a free-text task, a file or a symbol, seed a
  personalised PageRank and return the *minimal relevant subgraph within a token budget*.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from veridge.budget import estimate_tokens, select_within_budget
from veridge.impact import dependencies, dependents, expand_seed
from veridge.layers import layer_of, layer_summary
from veridge.model import Edge, EdgeType, Graph, Kind, Node
from veridge.rank import pagerank, top_ranked


def _area_of(path: str | None) -> str:
    if not path:
        return "(root)"
    return path.split("/")[0] if "/" in path else "(root)"


def project_map(graph: Graph, *, top: int = 8) -> dict[str, Any]:
    """Compact project digest, with the most-important nodes ranked by PageRank."""
    files = [n for n in graph.nodes.values() if n.kind is Kind.FILE]
    areas: dict[str, dict[str, Any]] = {}
    for n in files:
        a = _area_of(n.path)
        e = areas.setdefault(a, {"files": 0, "size": 0, "cats": {}})
        e["files"] += 1
        sz = int(n.meta.get("size", 0))
        e["size"] += sz
        cat = n.category.value if n.category else "?"
        e["cats"][cat] = e["cats"].get(cat, 0) + 1

    def _area_row(name: str, e: dict[str, Any]) -> dict[str, Any]:
        cats = sorted(e["cats"].items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        return {"area": name, "files": e["files"], "size": e["size"],
                "top_cats": [c for c, _ in cats]}

    area_rows = sorted((_area_row(a, e) for a, e in areas.items()),
                       key=lambda r: (-r["size"], r["area"]))[:top]

    scores = pagerank(graph)
    important = [{"id": nid, "kind": graph.nodes[nid].kind.value, "score": round(sc, 5)}
                 for nid, sc in top_ranked(scores, graph, limit=top)]

    counts = graph.counts()
    broken = sum(len(n.meta.get("broken_refs", [])) for n in graph.nodes.values())
    orphans = sum(1 for n in files if graph.is_orphan(n.id))
    return {
        "project": graph.project,
        "files": len(files),
        "symbols": counts["nodes"].get("symbol", 0),
        "areas": len(areas),
        "edges": len(graph.edges),
        "size": sum(int(n.meta.get("size", 0)) for n in files),
        "node_kinds": counts["nodes"],
        "edge_types": counts["edges"],
        "by_area": area_rows,
        "by_layer": layer_summary(graph),
        "most_important": important,
        "orphans": orphans,
        "broken_refs": broken,
    }


def find(graph: Graph, query: str, *, limit: int = 25) -> list[dict[str, Any]]:
    q = query.lower().strip()
    if not q:
        return []
    hits = [
        n for n in graph.nodes.values()
        if n.kind is not Kind.AREA
        and (q in n.label.lower() or (n.path and q in n.path.lower()) or q in n.id.lower())
    ]
    hits.sort(key=lambda n: n.id)
    return [{"id": n.id, "kind": n.kind.value, "path": n.path} for n in hits[:limit]]


def neighbors(graph: Graph, node_id: str) -> dict[str, Any] | None:
    n = graph.nodes.get(node_id)
    if n is None:
        return None

    def _row(other: str, etype: str) -> dict[str, Any]:
        k = graph.nodes[other].kind.value if other in graph.nodes else "?"
        return {"id": other, "kind": k, "edge": etype}

    out = [_row(e.target, e.type.value) for e in graph.out_edges(node_id)]
    inc = [_row(e.source, e.type.value) for e in graph.in_edges(node_id)]
    return {
        "id": n.id, "kind": n.kind.value, "path": n.path,
        "size": int(n.meta.get("size", 0)),
        "description": n.description,
        "broken_refs": n.meta.get("broken_refs", []),
        "outgoing": out, "incoming": inc,
    }


def resolve_seeds(graph: Graph, query: str, *, max_seeds: int = 25) -> list[str]:
    """Turn a free-text query / id / path into seed node ids for personalised ranking."""
    q = query.strip()
    if q in graph.nodes:
        return [q]
    low = q.lower()
    tokens = [t for t in low.replace("/", " ").replace(".", " ").split() if len(t) > 1]
    scored: list[tuple[int, str]] = []
    for n in graph.nodes.values():
        if n.kind is Kind.AREA:
            continue
        hay = f"{n.id} {n.label}".lower()
        if low in hay:
            hits = 3
        else:
            hits = sum(1 for t in tokens if t in hay)
        if hits:
            scored.append((hits * 100 + graph.degree(n.id), n.id))
    scored.sort(key=lambda kv: (-kv[0], kv[1]))
    return [nid for _, nid in scored[:max_seeds]]


def focus(graph: Graph, query: str, *, budget_tokens: int = 1500) -> dict[str, Any]:
    """Return the minimal relevant subgraph for ``query`` within ``budget_tokens``.

    Seeds are resolved from the query (an exact id/path, or fuzzy name matches), a personalised
    PageRank spreads relevance to their neighbourhood, and the highest-ranked nodes are admitted
    until the budget is spent. Edges among the admitted nodes are included for free.
    """
    seeds = resolve_seeds(graph, query)
    if not seeds:
        return {"query": query, "seeds": [], "budget_tokens": budget_tokens,
                "used_tokens": 0, "nodes": [], "edges": [],
                "note": "no nodes matched the query"}
    scores = pagerank(graph, seeds={s: 1.0 for s in seeds})
    ranked = [nid for nid, _ in top_ranked(scores, graph, limit=len(graph.nodes))]
    rows, used = select_within_budget(graph, ranked, budget_tokens)
    chosen = {r["id"] for r in rows}
    for r in rows:
        r["score"] = round(scores.get(r["id"], 0.0), 5)
    edges = [
        {"source": e.source, "target": e.target, "type": e.type.value}
        for e in graph.edges if e.source in chosen and e.target in chosen
    ]
    return {
        "query": query,
        "seeds": seeds[:10],
        "budget_tokens": budget_tokens,
        "used_tokens": used,
        "nodes": rows,
        "edges": edges,
    }


def impact(
    graph: Graph, query: str, *, seed_ids: list[str] | None = None,
    budget_tokens: int = 1500, hops: int | None = None, direction: str = "dependents",
) -> dict[str, Any]:
    """Blast-radius of a change: the affected subgraph, ranked and budgeted.

    Seeds come either from ``seed_ids`` (e.g. files changed in a diff) or by resolving
    ``query`` (an exact id/path, or fuzzy name matches). Each seed is lifted across
    granularity, then reverse reachability (``direction="dependents"``) collects everything
    affected — or forward reachability (``"dependencies"``) collects what the seed relies on.
    The affected set is ranked by a proximity-weighted personalised PageRank and trimmed to the
    token budget, so even a huge radius returns its *most important* members.
    """
    if seed_ids is not None:
        raw = [s for s in seed_ids if s in graph.nodes]
    else:
        raw = [query] if query in graph.nodes else resolve_seeds(graph, query, max_seeds=10)
    expanded: set[str] = set()
    for s in raw:
        expanded |= expand_seed(graph, s)
    base = {"query": query, "seeds": raw[:10], "direction": direction, "hops": hops,
            "budget_tokens": budget_tokens, "used_tokens": 0, "total_affected": 0,
            "nodes": [], "edges": []}
    if not expanded:
        base["note"] = "no nodes matched the seed"
        return base

    reach = (dependents(graph, expanded, hops=hops) if direction == "dependents"
             else dependencies(graph, expanded, hops=hops))
    affected = {nid: d for nid, d in reach.items() if d > 0}
    base["total_affected"] = len(affected)
    if not affected:
        base["note"] = "nothing depends on the seed — safe to change in isolation"
        return base

    scores = pagerank(graph, seeds={nid: 1.0 / (1 + d) for nid, d in affected.items()})
    ranked = [nid for nid, _ in top_ranked(scores, graph, limit=len(graph.nodes))
              if nid in affected]
    rows, used = select_within_budget(graph, ranked, budget_tokens)
    chosen = {r["id"] for r in rows}
    for r in rows:
        r["dist"] = affected.get(r["id"])
        r["score"] = round(scores.get(r["id"], 0.0), 5)
    base["used_tokens"] = used
    base["nodes"] = rows
    base["edges"] = [
        {"source": e.source, "target": e.target, "type": e.type.value}
        for e in graph.edges if e.source in chosen and e.target in chosen
    ]
    return base


def _resolve_one(graph: Graph, q: str) -> str | None:
    """Resolve a query to a single node id: exact id wins, else the best fuzzy match."""
    if q in graph.nodes:
        return q
    seeds = resolve_seeds(graph, q, max_seeds=1)
    return seeds[0] if seeds else None


def why(graph: Graph, a: str, b: str) -> dict[str, Any]:
    """Shortest typed path between two nodes — "how does A connect to B?".

    A breadth-first search over the (undirected) adjacency index returns the shortest chain,
    each step annotated with the edge type and the direction it points. Useful for questions
    like "how does the API layer reach the database?".
    """
    src, dst = _resolve_one(graph, a), _resolve_one(graph, b)
    base = {"a": a, "b": b, "resolved": [src, dst], "found": False, "length": 0, "path": []}
    if src is None or dst is None:
        base["note"] = "could not resolve both endpoints"
        return base
    if src == dst:
        base.update(found=True, length=0,
                    path=[{"id": src, "kind": graph.nodes[src].kind.value}])
        return base
    # BFS with parent tracking over undirected neighbours (deque -> O(1) dequeue).
    parent: dict[str, str] = {src: src}
    queue: deque[str] = deque([src])
    while queue:
        cur = queue.popleft()
        if cur == dst:
            break
        for nb in sorted(graph.neighbors(cur)):
            if nb not in parent:
                parent[nb] = cur
                queue.append(nb)
    if dst not in parent:
        base["note"] = "no path between the endpoints"
        return base
    chain: list[str] = []
    cur = dst
    while cur != src:
        chain.append(cur)
        cur = parent[cur]
    chain.append(src)
    chain.reverse()
    path = [{"id": chain[0], "kind": graph.nodes[chain[0]].kind.value}]
    for u, v in zip(chain, chain[1:], strict=False):
        etype, direction = _edge_between(graph, u, v)
        path.append({"id": v, "kind": graph.nodes[v].kind.value,
                     "edge": etype, "dir": direction})
    base.update(found=True, length=len(chain) - 1, path=path)
    return base


def _edge_between(graph: Graph, u: str, v: str) -> tuple[str, str]:
    """The edge type linking adjacent path nodes, and which way it points (->/<-)."""
    for e in graph.out_edges(u):
        if e.target == v:
            return e.type.value, "->"
    for e in graph.in_edges(u):
        if e.source == v:
            return e.type.value, "<-"
    return "?", "-"


def _file_of(graph: Graph, nid: str) -> str:
    n = graph.nodes.get(nid)
    if n is None:
        return nid
    return n.path if (n.kind is Kind.SYMBOL and n.path) else nid


_DEP_EDGES = (EdgeType.IMPORTS, EdgeType.REFERENCES, EdgeType.CALLS)


def tour(graph: Graph, *, budget_tokens: int = 2000, max_stops: int = 40) -> dict[str, Any]:
    """A dependency-ordered reading tour of the project's most important files.

    Takes the top files by global PageRank, orders them so a file's dependencies come before it
    (Kahn's algorithm on the collapsed file-level dependency graph; ties and cycles broken by
    PageRank), and emits a compact, budgeted "read these in this order, here's how each connects"
    walkthrough. Pure graph work — no model, no cost.
    """
    scores = pagerank(graph)
    files = [nid for nid, _ in top_ranked(scores, graph, kind=Kind.FILE, limit=max_stops)]
    cand = set(files)

    deps: dict[str, set[str]] = {f: set() for f in files}
    for e in graph.edges:
        if e.type not in _DEP_EDGES:
            continue
        u, v = _file_of(graph, e.source), _file_of(graph, e.target)
        if u in cand and v in cand and u != v:
            deps[u].add(v)
    used_by: dict[str, set[str]] = {f: set() for f in files}
    for u, vs in deps.items():
        for v in vs:
            used_by[v].add(u)

    # Kahn, foundational (depended-upon) first; break ties/cycles by PageRank.
    order: list[str] = []
    done: set[str] = set()
    remaining = set(files)
    while remaining:
        ready = [f for f in remaining if deps[f] <= done]
        pool = ready if ready else list(remaining)
        pick = max(pool, key=lambda f: (scores.get(f, 0.0), f))
        order.append(pick)
        done.add(pick)
        remaining.discard(pick)

    stops: list[dict[str, Any]] = []
    used = 0
    for i, fid in enumerate(order, 1):
        uses = sorted(deps[fid], key=lambda x: -scores.get(x, 0.0))[:3]
        ub = sorted(used_by[fid], key=lambda x: -scores.get(x, 0.0))[:3]
        stop = {"step": i, "id": fid, "layer": layer_of(graph.nodes[fid]),
                "score": round(scores.get(fid, 0.0), 5), "uses": uses, "used_by": ub}
        cost = estimate_tokens(f"{fid} {' '.join(uses)} {' '.join(ub)}")
        if stops and used + cost > budget_tokens:
            break
        stops.append(stop)
        used += cost
    return {"project": graph.project, "stops": stops, "total_files": len(files),
            "used_tokens": used, "budget_tokens": budget_tokens}


def subgraph_edges(graph: Graph, ids: set[str]) -> list[Edge]:
    return [e for e in graph.edges if e.source in ids and e.target in ids]


def induced_subgraph(graph: Graph, ids: set[str]) -> Graph:
    """A new graph containing ``ids`` (that exist) and the edges between them."""
    keep = {i for i in ids if i in graph.nodes}
    out = Graph(project=graph.project)
    for i in sorted(keep):
        n = graph.nodes[i]
        out.add_node(Node(id=n.id, kind=n.kind, label=n.label, path=n.path,
                          category=n.category, description=n.description, meta=dict(n.meta)))
    for e in graph.edges:
        if e.source in keep and e.target in keep:
            out.add_edge(Edge(e.source, e.target, e.type, dict(e.meta)))
    return out


def backbone(graph: Graph, *, limit: int = 1500) -> Graph:
    """A render-light core: the top-``limit`` nodes by PageRank, plus all area nodes."""
    scores = pagerank(graph)
    keep = {nid for nid, _ in top_ranked(scores, graph, limit=limit)}
    keep |= {n.id for n in graph.nodes.values() if n.kind is Kind.AREA}
    return induced_subgraph(graph, keep)
