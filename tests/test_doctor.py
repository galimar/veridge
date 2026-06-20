from __future__ import annotations

import json

from veridge import cli, doctor, integrate


def _names(checks):
    return {c.name: c for c in checks}


def test_diagnose_fresh_project_not_wired(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    cli.main(["build", str(tmp_path)])                 # build the index, nothing else
    checks = _names(doctor.diagnose(tmp_path))
    assert checks["index"].ok and not checks["index"].blocking   # index present
    assert checks["claude wired"].ok is False                    # integrate not run yet
    assert checks["codex wired"].ok is False


def test_diagnose_blocks_without_index(tmp_path):
    checks = _names(doctor.diagnose(tmp_path))
    assert checks["index"].ok is False and checks["index"].blocking is True


def test_diagnose_sees_wiring_after_integrate(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    cli.main(["build", str(tmp_path)])
    integrate.integrate_claude(tmp_path)
    integrate.integrate_codex(tmp_path)
    checks = _names(doctor.diagnose(tmp_path))
    assert checks["claude wired"].ok is True
    assert checks["codex wired"].ok is True


def test_doctor_cli_exit_codes_and_json(tmp_path, capsys):
    # no index yet -> blocking -> exit 1
    assert cli.main(["doctor", str(tmp_path)]) == 1
    capsys.readouterr()
    # build -> usable -> exit 0
    cli.main(["build", str(tmp_path)])
    capsys.readouterr()
    assert cli.main(["doctor", str(tmp_path)]) == 0
    capsys.readouterr()
    assert cli.main(["doctor", str(tmp_path), "--json"]) == 0
    data = {c["name"]: c for c in json.loads(capsys.readouterr().out)}
    assert data["index"]["ok"] is True
    assert data["claude wired"]["ok"] is False
