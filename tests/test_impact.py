from __future__ import annotations

from veridge import query
from veridge.impact import dependencies, dependents, expand_seed


def test_expand_seed_lifts_both_ways(graph):
    # A file seed pulls in the symbols it defines.
    assert "src/util.py#greet" in expand_seed(graph, "src/util.py")
    # A symbol seed pulls in its defining file.
    assert "src/util.py" in expand_seed(graph, "src/util.py#greet")


def test_dependents_reverse_reachability(graph):
    affected = dependents(graph, expand_seed(graph, "src/util.py"))
    # Direct dependents of util / greet.
    assert affected.get("src/app.py") == 1          # imports util
    assert affected.get("docs/guide.md") == 1       # references util in prose
    assert affected.get("src/app.py#run") == 1      # calls greet
    # Transitive: callers of run are two hops out.
    assert affected.get("src/app.py#App.start") == 2


def test_dependencies_forward(graph):
    deps = dependencies(graph, expand_seed(graph, "src/app.py#run"))
    assert "src/util.py#greet" in deps  # run calls greet
    assert "src/util.py" in deps        # app.py imports util.py


def test_query_impact_ranked_and_budgeted(graph):
    res = query.impact(graph, "src/util.py", budget_tokens=4000)
    ids = {r["id"] for r in res["nodes"]}
    assert res["total_affected"] >= 5
    assert {"src/app.py", "src/app.py#run", "docs/guide.md"} <= ids
    assert res["used_tokens"] <= 4000
    # Every shown node carries its distance and rank.
    assert all("dist" in r and "score" in r for r in res["nodes"])


def test_query_impact_hops_cap(graph):
    near = query.impact(graph, "src/util.py", hops=1, budget_tokens=4000)
    ids = {r["id"] for r in near["nodes"]}
    assert "src/app.py#run" in ids               # distance 1
    assert "src/app.py#App.start" not in ids     # distance 2, excluded by hops=1


def test_query_impact_budget_trims(graph):
    small = query.impact(graph, "src/util.py", budget_tokens=15)
    big = query.impact(graph, "src/util.py", budget_tokens=4000)
    assert len(small["nodes"]) < len(big["nodes"])


def test_query_impact_leaf_is_safe(graph):
    # Nothing points at the README, so changing it has no dependents.
    res = query.impact(graph, "README.md")
    assert res["total_affected"] == 0
    assert "safe to change" in res["note"]


def test_query_impact_seed_by_name(graph):
    res = query.impact(graph, "greet", budget_tokens=4000)
    ids = {r["id"] for r in res["nodes"]}
    assert "src/app.py#run" in ids  # resolved 'greet' -> its callers


def test_query_impact_explicit_seed_ids_diff_mode(graph):
    # Simulates --diff: seeds handed in directly (e.g. from `git diff --name-only`).
    res = query.impact(graph, "diff", seed_ids=["src/util.py"], budget_tokens=4000)
    assert res["total_affected"] >= 5
    assert any(r["id"] == "src/app.py" for r in res["nodes"])
