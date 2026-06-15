from __future__ import annotations

from veridge.model import Edge, EdgeType, Graph, Kind, Node


def _g() -> Graph:
    g = Graph("p")
    g.add_node(Node("a", Kind.FILE, "a", path="a"))
    g.add_node(Node("b", Kind.FILE, "b", path="b"))
    g.add_node(Node("c", Kind.FILE, "c", path="c"))
    g.add_edge(Edge("a", "b", EdgeType.IMPORTS))
    g.add_edge(Edge("b", "c", EdgeType.IMPORTS))
    return g


def test_edges_dedupe():
    g = _g()
    assert g.add_edge(Edge("a", "b", EdgeType.IMPORTS)) is False
    assert len(g.edges) == 2


def test_adjacency_directions():
    g = _g()
    assert g.degree("b") == 2
    assert [e.target for e in g.out_edges("b")] == ["c"]
    assert [e.source for e in g.in_edges("b")] == ["a"]
    assert g.neighbors("b") == {"a", "c"}


def test_undirected_weights_symmetric():
    g = _g()
    adj = g.undirected_weights()
    assert adj["a"]["b"] == adj["b"]["a"]
    assert "c" in adj["b"] and "a" in adj["b"]


def test_roundtrip_preserves_graph_and_indices():
    g = _g()
    g.add_node(Node("s", Kind.SYMBOL, "s", path="a"))
    g.add_edge(Edge("a", "s", EdgeType.DEFINES))
    g2 = Graph.from_dict(g.to_dict())
    assert set(g2.nodes) == set(g.nodes)
    assert g2.degree("b") == 2
    assert [e.target for e in g2.out_edges("a")] == sorted([e.target for e in g.out_edges("a")]) \
        or {e.target for e in g2.out_edges("a")} == {e.target for e in g.out_edges("a")}


def test_counts():
    g = _g()
    c = g.counts()
    assert c["nodes"]["file"] == 3
    assert c["edges"]["imports"] == 2


def test_deterministic_json():
    assert _g().to_json() == _g().to_json()
