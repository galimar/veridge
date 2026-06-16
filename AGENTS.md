# AGENTS.md — working on Veridge

Veridge builds an always-fresh, low-token **graph of a whole project** (files + symbols + areas +
decisions + git sessions), ranks it with PageRank, and serves token-budgeted slices to AI
assistants and humans. The core has **zero runtime dependencies** (Python standard library only).

## Setup & checks

```bash
pip install -e ".[dev,mcp,treesitter]"
ruff check veridge tests      # must pass
pytest -q                     # must pass
```

Every change must keep **ruff** and **pytest** green, and add/adjust tests for behaviour changes.

## Design principles (do not break)

**read-only** on the user's sources · **zero-deps core** (any new dependency goes behind an
optional extra, never in the core) · **low-token** (queries return structure, never file
contents) · **ranked** (relevance from the graph, not raw counts) · **deterministic** (nodes and
edges are sorted on serialization → reproducible `graph.json`). **No LLM builds the graph.**

## Layout

- `model.py` — typed nodes/edges + indexed adjacency (O(degree) queries)
- `walk.py` / `ignore.py` / `classify.py` — file enumeration and typing
- `parse_python.py` (stdlib `ast`) + `treesitter.py` (optional extra) — symbols, imports, calls
- `parse_docs.py` — references (links / wikilinks / prose paths) + decision ids
- `indexer.py` — assembles the graph; `sessions.py` — git history
- `rank.py` (PageRank) · `budget.py` (token cost) · `query.py` (map / find / neighbors / focus /
  impact / tour / why)
- `freshness.py` (manifest + anti-drift gate) · `store.py` (`.veridge/`) · `watch.py` ·
  `export.py` · `integrate.py`
- `viewer.py` + `ui/template.html` — offline canvas graph · `cli.py` · `mcp_server.py`

## More

`README.md` (usage), `ROADMAP.md` (plan & what's intentionally out of scope), `CONTRIBUTING.md`
(PR guidance), `docs/graph-format.md` (the `graph.json` schema).
