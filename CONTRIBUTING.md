# Contributing to Veridge

Thanks for considering a contribution! Veridge is young — issues, ideas and PRs are all
welcome.

## Getting started

```bash
pip install -e ".[dev,mcp,treesitter]"
ruff check veridge tests
pytest -q
```

Tests for the optional tree-sitter extra skip automatically when it isn't installed
(`pytest.importorskip`), so the core suite runs with zero runtime dependencies.

## Design principles (please keep these intact)

These are the spine of the project — a change that breaks one of them needs a very good reason:

- **read-only** on the user's sources — Veridge indexes, it never modifies your files.
- **zero-deps core** — the core runs on the Python standard library alone. New dependencies go
  behind an optional extra (like `[treesitter]` / `[mcp]`), never in the core.
- **low-token** — queries return ids, types, sizes and connections, never file contents.
- **ranked** — relevance comes from the graph (PageRank), so answers are useful, not just complete.
- **deterministic** — nodes and edges are sorted on serialization; the same input yields the same
  `graph.json`. No LLM is used to *build* the graph.

## Pull requests

- Keep the diff focused; match the surrounding style.
- Add or update tests for behaviour changes; `ruff` and `pytest` must pass.
- For larger features, check [ROADMAP.md](ROADMAP.md) first or open an issue to discuss.

## Reporting issues

Bug reports with a minimal repro are gold. Security-sensitive reports: please open a private
advisory rather than a public issue.
