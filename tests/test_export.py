from __future__ import annotations

import json

import pytest

from veridge import cli, export


def test_schema_version_in_graph_json(graph):
    assert graph.to_dict()["schema_version"] >= 1


def test_jgf_shape(graph):
    g = export.to_jgf(graph)["graph"]
    assert g["directed"] is True
    assert g["metadata"]["schema_version"] >= 1
    assert g["nodes"]["src/util.py"]["metadata"]["kind"] == "file"
    rels = {(e["source"], e["target"], e["relation"]) for e in g["edges"]}
    assert ("src/app.py", "src/util.py", "imports") in rels


def test_dot_output(graph):
    dot = export.to_dot(graph)
    assert dot.startswith("digraph")
    assert "->" in dot
    assert '"src/util.py"' in dot


def test_export_dispatch(graph):
    native = json.loads(export.export(graph, "native"))
    assert native["schema_version"] >= 1
    assert "graph" in json.loads(export.export(graph, "jgf"))
    assert export.export(graph, "dot").startswith("digraph")
    with pytest.raises(ValueError):
        export.export(graph, "nope")


def test_export_cli_stdout(project, capsys):
    cli.main(["build", str(project)])
    capsys.readouterr()  # discard the build summary so only the export is captured
    assert cli.main(["export", str(project), "--format", "jgf"]) == 0
    assert "graph" in json.loads(capsys.readouterr().out)


def test_export_cli_out_file(project, tmp_path, capsys):
    cli.main(["build", str(project)])
    target = tmp_path / "g.dot"
    assert cli.main(["export", str(project), "--format", "dot", "--out", str(target)]) == 0
    assert target.read_text(encoding="utf-8").startswith("digraph")
