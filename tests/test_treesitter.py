from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_language_pack")

from veridge.model import EdgeType, Kind  # noqa: E402
from veridge.treesitter import available, extract_symbols  # noqa: E402


def test_available():
    assert available() is True


def test_js_symbols_and_calls():
    syms = extract_symbols(
        ".js", "function greet(n){ return n }\nclass App { start(){ return greet(1) } }\n")
    by_qual = {s.qualname: s for s in syms}
    assert {"greet", "App", "App.start"} <= set(by_qual)
    assert by_qual["App"].kind == "class"
    assert "greet" in by_qual["App.start"].calls


def test_go_symbols_and_calls():
    syms = extract_symbols(
        ".go", "package m\nfunc greet() int { return 1 }\nfunc Run() int { return greet() }\n")
    by_qual = {s.qualname: s for s in syms}
    assert {"greet", "Run"} <= set(by_qual)
    assert "greet" in by_qual["Run"].calls


def test_rust_symbols():
    syms = extract_symbols(
        ".rs", "struct App;\nfn greet() -> i32 { 1 }\nfn run() -> i32 { greet() }\n")
    by_qual = {s.qualname: s for s in syms}
    assert {"App", "greet", "run"} <= set(by_qual)
    assert by_qual["App"].kind == "class"
    assert "greet" in by_qual["run"].calls


def test_java_symbols():
    src = ("class App { String greet(String n){ return n; } "
           "String run(){ return greet(\"x\"); } }")
    syms = extract_symbols(".java", src)
    by_qual = {s.qualname: s for s in syms}
    assert "App" in by_qual and "App.run" in by_qual
    assert "greet" in by_qual["App.run"].calls


def test_unsupported_extension_returns_none():
    assert extract_symbols(".cobol", "anything") is None


def test_malformed_source_is_safe():
    # tree-sitter is error-tolerant: never raises, returns a (possibly partial) list, not None.
    res = extract_symbols(".js", "function (((")
    assert res is not None


def test_indexer_builds_js_symbol_and_call_graph(tmp_path):
    (tmp_path / "a.js").write_text(
        "export function greet(n){ return n }\nclass App { run(){ return greet(1) } }\n",
        encoding="utf-8")
    from veridge.freshness import index
    g, _ = index(tmp_path)
    sym_ids = {n.id for n in g.nodes.values() if n.kind is Kind.SYMBOL}
    assert "a.js#greet" in sym_ids
    assert "a.js#App.run" in sym_ids
    calls = {(e.source, e.target) for e in g.edges if e.type is EdgeType.CALLS}
    assert ("a.js#App.run", "a.js#greet") in calls
