from __future__ import annotations

from veridge.model import EdgeType, Kind


def _edges(graph, etype):
    return {(e.source, e.target) for e in graph.edges if e.type is etype}


def test_file_and_area_nodes(graph):
    files = [n for n in graph.nodes.values() if n.kind is Kind.FILE]
    assert len(files) == 7
    areas = {n.label for n in graph.nodes.values() if n.kind is Kind.AREA}
    assert {"(root)", "src", "docs", "data"} <= areas


def test_symbols_are_nodes(graph):
    syms = {n.id for n in graph.nodes.values() if n.kind is Kind.SYMBOL}
    assert "src/app.py#App.start" in syms
    assert "src/util.py#greet" in syms
    assert len([s for s in syms]) == 4


def test_defines_edges(graph):
    assert ("src/util.py", "src/util.py#greet") in _edges(graph, EdgeType.DEFINES)


def test_imports_edge_file_level(graph):
    assert ("src/app.py", "src/util.py") in _edges(graph, EdgeType.IMPORTS)


def test_call_graph_symbol_level(graph):
    calls = _edges(graph, EdgeType.CALLS)
    assert ("src/app.py#run", "src/util.py#greet") in calls
    assert ("src/app.py#App.start", "src/app.py#run") in calls


def test_references_include_prose_mention(graph):
    refs = _edges(graph, EdgeType.REFERENCES)
    assert ("docs/guide.md", "src/util.py") in refs   # plain prose mention
    assert ("README.md", "src/util.py") in refs       # markdown link


def test_broken_link_recorded(graph):
    readme = graph.nodes["README.md"]
    assert "src/missing.py" in readme.meta.get("broken_refs", [])


def test_decisions_and_mentions(graph):
    assert "decision:ADR-7" in graph.nodes
    mentions = _edges(graph, EdgeType.MENTIONS)
    assert ("README.md", "decision:ADR-7") in mentions
    assert ("docs/guide.md", "decision:ADR-7") in mentions


def test_data_file_not_read_but_indexed(graph):
    assert "data/big.csv" in graph.nodes
    assert graph.nodes["data/big.csv"].category.value == "data"
