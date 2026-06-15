from __future__ import annotations

from veridge import query


def test_why_direct_import(graph):
    res = query.why(graph, "src/app.py", "src/util.py")
    assert res["found"] is True
    assert res["length"] == 1
    assert res["path"][0]["id"] == "src/app.py"
    assert res["path"][-1]["id"] == "src/util.py"
    assert res["path"][-1]["edge"] == "imports"


def test_why_transitive_calls(graph):
    res = query.why(graph, "App.start", "greet")  # resolved by name
    assert res["found"] is True
    assert res["resolved"][0] == "src/app.py#App.start"
    assert res["resolved"][1] == "src/util.py#greet"
    assert res["length"] >= 1


def test_why_no_path_for_isolated(graph):
    # data/big.csv links only to its area; it can't reach the README.
    res = query.why(graph, "data/big.csv", "README.md")
    assert res["found"] is False


def test_why_unresolved(graph):
    res = query.why(graph, "zzz-nope", "README.md")
    assert res["found"] is False
    assert "resolve" in res["note"]


def test_tour_orders_dependencies_first(graph):
    res = query.tour(graph, budget_tokens=4000)
    ids = [s["id"] for s in res["stops"]]
    assert ids  # non-empty
    # util is imported by app -> util must be toured before app.
    assert ids.index("src/util.py") < ids.index("src/app.py")


def test_tour_reports_connections(graph):
    res = query.tour(graph, budget_tokens=4000)
    app = next(s for s in res["stops"] if s["id"] == "src/app.py")
    assert "src/util.py" in app["uses"]
    util = next(s for s in res["stops"] if s["id"] == "src/util.py")
    assert "src/app.py" in util["used_by"]


def test_tour_respects_budget(graph):
    small = query.tour(graph, budget_tokens=10)
    big = query.tour(graph, budget_tokens=4000)
    assert len(small["stops"]) <= len(big["stops"])
    assert small["used_tokens"] <= 10 or len(small["stops"]) == 1
