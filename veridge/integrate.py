"""Wire Veridge into an AI coding assistant: register the MCP server + add a steering note.

The ``veridge-mcp`` server is plain MCP, so it already works with any MCP-aware assistant; what
differs per tool is the *glue* — where the server is registered and which file the assistant
reads for project instructions. This module writes that glue, **project-local and idempotent**,
never touching a global user config:

* **Claude Code** — a ``.mcp.json`` entry (project-scoped) + a marked block in ``CLAUDE.md``.
* **Codex** — a ``[mcp_servers.veridge]`` table in a project ``.codex/config.toml`` + a marked
  block in ``AGENTS.md``.

The steering note tells the assistant to *prefer Veridge's ranked, budgeted queries over
re-reading files*. Requires the ``[mcp]`` extra (``pip install "veridge[mcp]"``) so that the
``veridge-mcp`` command exists.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# The MCP server entry (stdio). args=["."] -> index the directory the assistant launches it in.
_MCP_ENTRY = {"type": "stdio", "command": "veridge-mcp", "args": ["."]}

_START, _END = "<!-- veridge:start -->", "<!-- veridge:end -->"
_DIRECTIVE = f"""{_START}
## Project map (Veridge)

This project has a Veridge index (`.veridge/`). Before re-reading or grepping files to
understand the codebase, prefer the **`veridge` MCP tools** — they return ranked, token-budgeted
*structure*, never file contents:

- `project_map` — orient: areas, layers, the most-important files (by PageRank).
- `focus "<task>"` — the minimal relevant subgraph for a task, within a token budget.
- `impact <file|symbol>` — what a change affects (blast-radius).
- `find` / `neighbors` / `why` / `tour` — locate, inspect, explain a path, walk the key files.

If `health` reports the index is stale, rebuild it with `veridge build .`.
{_END}
"""


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _add_directive(doc: Path) -> None:
    """Append the steering block to ``doc`` (create it if absent; skip if already present)."""
    existing = doc.read_text(encoding="utf-8", errors="ignore") if doc.exists() else ""
    if _START in existing:
        return
    prefix = existing.rstrip() + "\n\n" if existing.strip() else ""
    _write(doc, prefix + _DIRECTIVE)


def integrate_claude(root: str | os.PathLike[str]) -> list[Path]:
    """Register the MCP server in ``.mcp.json`` and add the steering note to ``CLAUDE.md``."""
    root_p = Path(root)
    mcp = root_p / ".mcp.json"
    data: dict = {}
    if mcp.exists():
        try:
            loaded = json.loads(mcp.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise RuntimeError(f"{mcp} is not valid JSON; leaving it untouched") from exc
        if isinstance(loaded, dict):
            data = loaded
    servers = data.setdefault("mcpServers", {})
    if servers.get("veridge") != _MCP_ENTRY:
        servers["veridge"] = dict(_MCP_ENTRY)
        _write(mcp, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    claude = root_p / "CLAUDE.md"
    _add_directive(claude)
    return [mcp, claude]


def integrate_codex(root: str | os.PathLike[str]) -> list[Path]:
    """Register the MCP server in ``.codex/config.toml`` and add the note to ``AGENTS.md``."""
    root_p = Path(root)
    cfg = root_p / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    existing = cfg.read_text(encoding="utf-8", errors="ignore") if cfg.exists() else ""
    if "[mcp_servers.veridge]" not in existing:
        block = '[mcp_servers.veridge]\ncommand = "veridge-mcp"\nargs = ["."]\n'
        prefix = existing.rstrip() + "\n\n" if existing.strip() else ""
        _write(cfg, prefix + block)
    agents = root_p / "AGENTS.md"
    _add_directive(agents)
    return [cfg, agents]


def integrate(root: str | os.PathLike[str], assistant: str) -> list[Path]:
    """Dispatch to :func:`integrate_claude` or :func:`integrate_codex`."""
    if assistant == "claude":
        return integrate_claude(root)
    if assistant == "codex":
        return integrate_codex(root)
    raise ValueError(f"unknown assistant {assistant!r}; choose 'claude' or 'codex'")
