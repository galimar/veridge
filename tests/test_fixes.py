from __future__ import annotations

import json

from veridge import budget, query
from veridge.freshness import build_manifest, diff_manifest, find_orphans
from veridge.model import Edge, EdgeType
from veridge.parse_python import parse_python


def test_class_does_not_steal_method_calls():
    src = "class A:\n    def m(self):\n        return helper()\n"
    syms = {s.qualname: s for s in parse_python(src).symbols}
    assert "helper" in syms["A.m"].calls       # the method owns the call
    assert "helper" not in syms["A"].calls      # the class no longer double-counts it


def test_row_cost_uses_json(graph):
    row = budget.node_row(graph, "src/util.py")
    assert budget._row_cost(row) == budget.estimate_tokens(json.dumps(row, ensure_ascii=False))


def test_orphan_definitions_agree(graph):
    m = query.project_map(graph)
    assert m["orphans"] == len(find_orphans(graph))   # digest and gate share one predicate
    assert graph.is_orphan("config.toml") is True     # only its area edge
    assert graph.is_orphan("src/util.py") is False    # imported / referenced / defines


def test_undirected_weights_cached_and_invalidated(graph):
    a = graph.undirected_weights()
    assert graph.undirected_weights() is a                       # cached: same object
    graph.add_edge(Edge("config.toml", "src/util.py", EdgeType.REFERENCES))
    assert graph.undirected_weights() is not a                   # add_edge invalidates it


def test_data_file_change_detected(project):
    m1 = build_manifest(project)
    (project / "data" / "big.csv").write_text("a,b,c\n1,2,3\n9,9,9\n", encoding="utf-8")
    m2 = build_manifest(project)
    assert "data/big.csv" in diff_manifest(m1, m2)["changed"]
