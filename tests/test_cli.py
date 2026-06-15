from __future__ import annotations

from veridge import cli


def test_build_then_map(project, capsys):
    assert cli.main(["build", str(project)]) == 0
    assert (project / ".veridge" / "graph.json").is_file()
    assert cli.main(["map", str(project)]) == 0
    out = capsys.readouterr().out
    assert "most important (PageRank)" in out


def test_focus_cli(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["focus", "util", str(project), "--budget", "600"]) == 0
    out = capsys.readouterr().out
    assert "focus 'util'" in out
    assert "src/util.py" in out


def test_impact_cli(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["impact", "src/util.py", str(project), "--budget", "2000"]) == 0
    out = capsys.readouterr().out
    assert "impact (dependents)" in out
    assert "src/app.py" in out


def test_impact_cli_deps_direction(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["impact", "src/app.py#run", str(project), "--deps", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"dependencies"' in out
    assert "src/util.py#greet" in out


def test_gate_cli_red_on_broken(project, capsys):
    cli.main(["build", str(project)])
    rc = cli.main(["gate", str(project)])
    out = capsys.readouterr().out
    assert "broken references: 1" in out
    assert rc == 1


def test_find_cli(project, capsys):
    cli.main(["build", str(project)])
    cli.main(["find", "greet", str(project)])
    assert "src/util.py#greet" in capsys.readouterr().out


def test_map_json(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["map", str(project), "--json"]) == 0
    out = capsys.readouterr().out
    assert '"most_important"' in out
    assert '"by_layer"' in out


def test_why_cli(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["why", "src/app.py", "src/util.py", str(project)]) == 0
    out = capsys.readouterr().out
    assert "imports" in out


def test_tour_cli(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["tour", str(project), "--budget", "3000"]) == 0
    out = capsys.readouterr().out
    assert "tour of" in out
    assert "src/util.py" in out
