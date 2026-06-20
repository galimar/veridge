"""``veridge doctor``: a read-only setup check for the current project.

Answers the first question a new collaborator or agent has — *"is Veridge wired up correctly
here?"* — without touching anything. It reports what Veridge can actually verify from the project:
the index, the optional extras, and the **per-assistant** MCP registration + steering note.

It deliberately does **not** claim anything about the assistant's *running* MCP client (Veridge
can't see that): it checks the project files that configure it. If the MCP tools aren't available
in your client, the `veridge` CLI is always the fallback — every MCP tool has a CLI twin.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from veridge import integrate, store, treesitter

_CODEX_MARKER = "[mcp_servers.veridge]"


@dataclass
class Check:
    """One setup fact. ``blocking`` means Veridge is unusable until it's fixed (no index)."""

    name: str
    ok: bool
    detail: str
    blocking: bool = False


def _file_has(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _mcp_json_has_veridge(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return isinstance(servers, dict) and "veridge" in servers


def diagnose(root: str | os.PathLike[str]) -> list[Check]:
    """Return the setup checks for the project at ``root``, read-only."""
    root_p = Path(root)

    built = (store.store_dir(root_p) / "graph.json").is_file()
    has_mcp_cmd = shutil.which("veridge-mcp") is not None
    ts = treesitter.available()
    claude_ok = (_mcp_json_has_veridge(root_p / ".mcp.json")
                 and _file_has(root_p / "CLAUDE.md", integrate._START))
    codex_ok = (_file_has(root_p / ".codex" / "config.toml", _CODEX_MARKER)
                and _file_has(root_p / "AGENTS.md", integrate._START))
    gitignore = root_p / ".gitignore"
    ignored = _file_has(gitignore, ".veridge")

    checks = [
        Check("index", built,
              "`.veridge/graph.json` present" if built
              else "no index — run `veridge build .`",
              blocking=not built),
        Check("mcp server", has_mcp_cmd,
              "`veridge-mcp` on PATH" if has_mcp_cmd
              else 'MCP extra missing: pip install "veridge[mcp]" '
                   "(the CLI works without it)"),
        Check("treesitter extra", ts,
              "multi-language symbols enabled" if ts
              else 'Python-only symbols; for JS/TS/Go/… : pip install "veridge[treesitter]"'),
        Check("claude wired", claude_ok,
              ".mcp.json + CLAUDE.md note present" if claude_ok
              else "run `veridge integrate claude`"),
        Check("codex wired", codex_ok,
              ".codex/config.toml + AGENTS.md note present" if codex_ok
              else "run `veridge integrate codex`"),
    ]
    if gitignore.exists():                       # only meaningful when the project uses git
        checks.append(Check("index gitignored", ignored,
                            "`.veridge/` is gitignored" if ignored
                            else "add `.veridge/` to .gitignore — don't commit the index"))
    return checks
