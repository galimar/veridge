from __future__ import annotations

from veridge import query


def test_project_map_shape(graph):
    m = query.project_map(graph)
    assert m["files"] == 7
    assert m["symbols"] == 4
    assert m["broken_refs"] == 1
    assert m["most_important"]  # PageRank-ranked, non-empty
    assert m["orphans"] >= 2
    layers = {ly["layer"] for ly in m["by_layer"]}
    assert {"entrypoint", "util", "docs"} <= layers


def test_find(graph):
    res = query.find(graph, "util")
    ids = {r["id"] for r in res}
    assert "src/util.py" in ids
    assert "src/util.py#greet" in ids


def test_neighbors_directions(graph):
    n = query.neighbors(graph, "src/util.py")
    assert n is not None
    incoming_ids = {o["id"] for o in n["incoming"]}
    assert "src/app.py" in incoming_ids  # imported by app


def test_neighbors_unknown(graph):
    assert query.neighbors(graph, "nope") is None


def test_focus_seeds_from_query(graph):
    res = query.focus(graph, "util", budget_tokens=500)
    assert "src/util.py" in res["seeds"]
    ids = {r["id"] for r in res["nodes"]}
    # The seed and its caller should surface in the relevant subgraph.
    assert "src/util.py" in ids
    assert res["used_tokens"] <= 500 or len(res["nodes"]) == 1


def test_focus_respects_budget(graph):
    small = query.focus(graph, "app", budget_tokens=20)
    big = query.focus(graph, "app", budget_tokens=4000)
    assert len(small["nodes"]) <= len(big["nodes"])


def test_focus_no_match(graph):
    res = query.focus(graph, "zzzznotfound")
    assert res["nodes"] == []
