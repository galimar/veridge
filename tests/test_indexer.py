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


def test_ts_esm_and_workspace_imports(tmp_path):
    """TS imports resolve the ESM `.js`->`.ts` convention and bare workspace packages.

    NodeNext TypeScript writes the runtime extension in specifiers (`./util.js` for a
    `util.ts`), and npm/yarn/pnpm monorepos import packages by their package.json `name`
    (`@scope/kernel`). Both must resolve to real file nodes. Regex-based — no extra needed.
    """
    from veridge.indexer import build_graph

    (tmp_path / "packages/kernel/src").mkdir(parents=True)
    (tmp_path / "packages/kernel/package.json").write_text(
        '{"name": "@scope/kernel"}', encoding="utf-8")
    (tmp_path / "packages/kernel/src/index.ts").write_text(
        "export const k = 1;\n", encoding="utf-8")
    (tmp_path / "apps/web/src").mkdir(parents=True)
    (tmp_path / "apps/web/src/util.ts").write_text("export const u = 2;\n", encoding="utf-8")
    (tmp_path / "apps/web/src/main.ts").write_text(
        'import { u } from "./util.js";\nimport { k } from "@scope/kernel";\n', encoding="utf-8")

    # ESM `.js` -> `.ts`, and a bare workspace package -> its source entry
    imports = _edges(build_graph(tmp_path, sessions=False), EdgeType.IMPORTS)
    assert ("apps/web/src/main.ts", "apps/web/src/util.ts") in imports
    assert ("apps/web/src/main.ts", "packages/kernel/src/index.ts") in imports


def test_root_level_workspace_package_resolves(tmp_path):
    """A package.json at the repo root (pkg_dir == "") must still resolve by name.

    Regression guard: the package dir is "" there, so a naive join produced absolute
    "/src/index" candidates that never matched the slash-free node ids.
    """
    from veridge.indexer import build_graph

    (tmp_path / "src").mkdir()
    (tmp_path / "package.json").write_text('{"name": "rootpkg"}', encoding="utf-8")
    (tmp_path / "src/index.ts").write_text("export const r = 1;\n", encoding="utf-8")
    (tmp_path / "consumer.ts").write_text(
        'import { r } from "rootpkg";\n', encoding="utf-8")

    imports = _edges(build_graph(tmp_path, sessions=False), EdgeType.IMPORTS)
    assert ("consumer.ts", "src/index.ts") in imports


def test_malformed_package_json_does_not_abort_build(tmp_path):
    """A non-object / invalid package.json is skipped, never crashing the index build."""
    from veridge.indexer import build_graph

    (tmp_path / "a").mkdir()
    (tmp_path / "a/package.json").write_text("[1, 2, 3]", encoding="utf-8")    # JSON, not an object
    (tmp_path / "b").mkdir()
    (tmp_path / "b/package.json").write_text("{not valid", encoding="utf-8")   # not JSON at all
    (tmp_path / "main.ts").write_text("export const x = 1;\n", encoding="utf-8")

    g = build_graph(tmp_path, sessions=False)   # must not raise
    assert "main.ts" in g.nodes
