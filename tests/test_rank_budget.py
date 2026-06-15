from __future__ import annotations

from veridge.budget import node_row, select_within_budget
from veridge.rank import pagerank, top_ranked


def test_pagerank_is_a_distribution(graph):
    scores = pagerank(graph)
    assert abs(sum(scores.values()) - 1.0) < 1e-6
    assert all(s >= 0 for s in scores.values())


def test_personalised_pagerank_biases_seeds(graph):
    seed = "src/util.py"
    uniform = pagerank(graph)
    personalised = pagerank(graph, seeds={seed: 1.0})
    # Restarting on the seed must lift it relative to the uniform ranking.
    assert personalised[seed] > uniform[seed]


def test_top_ranked_filters_by_kind(graph):
    from veridge.model import Kind
    scores = pagerank(graph)
    files = top_ranked(scores, graph, kind=Kind.FILE, limit=3)
    assert files and all(graph.nodes[i].kind is Kind.FILE for i, _ in files)


def test_budget_is_respected(graph):
    scores = pagerank(graph)
    ranked = [i for i, _ in top_ranked(scores, graph, limit=len(graph.nodes))]
    rows, used = select_within_budget(graph, ranked, budget_tokens=30)
    assert used <= 30 or len(rows) == 1  # never empty, otherwise within budget
    assert len(rows) < len(ranked)       # the budget actually trims


def test_node_row_has_no_contents(graph):
    row = node_row(graph, "src/util.py")
    assert "size" in row and "deg" in row
    assert "content" not in row and "text" not in row
