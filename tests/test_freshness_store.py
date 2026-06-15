from __future__ import annotations

from veridge import store
from veridge.freshness import build_manifest, diff_manifest, evaluate, index


def test_manifest_diff_detects_change(project):
    m1 = build_manifest(project)
    (project / "src" / "util.py").write_text("def greet(n):\n    return n\n", encoding="utf-8")
    (project / "new.md").write_text("new\n", encoding="utf-8")
    m2 = build_manifest(project)
    d = diff_manifest(m1, m2)
    assert "new.md" in d["added"]
    assert "src/util.py" in d["changed"]


def test_gate_reports_broken_and_orphans(graph, project):
    m = build_manifest(project)
    rep = evaluate(graph, m, m)
    assert rep.stale_count == 0
    assert ("README.md", "src/missing.py") in rep.broken
    assert "config.toml" in rep.orphans
    assert rep.ok is False  # a broken ref keeps the gate red


def test_gate_ok_when_clean(project):
    # A project with no broken refs and a matching manifest is green.
    (project / "README.md").write_text("# clean\n", encoding="utf-8")
    g, m = index(project)
    rep = evaluate(g, m, m)
    assert rep.broken == []
    assert rep.ok is True


def test_store_roundtrip(graph, project):
    _, m = index(project)
    store.save(project, graph, m)
    g2 = store.load_graph(project)
    m2 = store.load_manifest(project)
    assert g2 is not None and m2 is not None
    assert set(g2.nodes) == set(graph.nodes)
    assert g2.degree("src/util.py") == graph.degree("src/util.py")


def test_load_missing_is_none(tmp_path):
    assert store.load_graph(tmp_path) is None
    assert store.load_manifest(tmp_path) is None
