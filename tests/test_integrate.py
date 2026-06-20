from __future__ import annotations

import json

import pytest

from veridge import cli, integrate


def test_integrate_claude_creates_files(tmp_path):
    integrate.integrate_claude(tmp_path)
    mcp = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    entry = mcp["mcpServers"]["veridge"]
    assert entry["command"] == "veridge-mcp" and entry["args"] == ["."] and entry["type"] == "stdio"
    claude = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Veridge" in claude and "veridge:start" in claude


def test_integrate_claude_merges_and_is_idempotent(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"type": "stdio", "command": "x"}}}), encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# My project\n\nExisting notes.\n", encoding="utf-8")
    integrate.integrate_claude(tmp_path)
    integrate.integrate_claude(tmp_path)              # run twice
    mcp = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert "other" in mcp["mcpServers"] and "veridge" in mcp["mcpServers"]   # merged, not clobbered
    claude = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# My project")          # existing content kept
    assert claude.count("veridge:start") == 1         # directive not duplicated


def test_integrate_refreshes_stale_directive_in_place(tmp_path):
    """Re-running integrate replaces an old directive block, preserving surrounding content."""
    stale = (
        "# My project\n\nIntro.\n\n"
        f"{integrate._START}\nOLD veridge note that should be replaced\n{integrate._END}\n\n"
        "## Footer kept below\n"
    )
    (tmp_path / "CLAUDE.md").write_text(stale, encoding="utf-8")
    integrate.integrate_claude(tmp_path)
    claude = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "OLD veridge note" not in claude              # stale content gone
    assert "AGENT_PLAYBOOK.md" in claude                 # current directive written
    assert claude.count(integrate._START) == 1           # still a single block
    assert claude.startswith("# My project")             # content before the block kept
    assert "## Footer kept below" in claude              # content after the block kept


def test_integrate_claude_rejects_bad_json(tmp_path):
    (tmp_path / ".mcp.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        integrate.integrate_claude(tmp_path)


def test_integrate_codex_creates_files_and_idempotent(tmp_path):
    integrate.integrate_codex(tmp_path)
    integrate.integrate_codex(tmp_path)
    toml = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert toml.count("[mcp_servers.veridge]") == 1   # registered once, not duplicated
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.count("veridge:start") == 1


def test_integrate_dispatch_unknown():
    with pytest.raises(ValueError):
        integrate.integrate(".", "nope")


def test_integrate_cli(tmp_path, capsys):
    assert cli.main(["integrate", "claude", str(tmp_path)]) == 0
    assert (tmp_path / ".mcp.json").is_file() and (tmp_path / "CLAUDE.md").is_file()
    assert "integrated veridge for claude" in capsys.readouterr().out
