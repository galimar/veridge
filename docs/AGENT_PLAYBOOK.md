# Veridge — Agent Playbook

**Audience: AI coding agents (Claude Code, Codex) working in a repo that uses — or is about to
use — Veridge.** Read this before acting. Humans: see [`PROMPTS.md`](PROMPTS.md) for ready-to-paste
requests that point an agent at the right section here.

Veridge is the same tool for both assistants: a plain, deterministic MCP server over a read-only
graph. Claude and Codex are expected to work **alternately and collaboratively** on the same repo
through that one shared graph.

---

## 0. What Veridge is, and the golden rules

Veridge builds a deterministic, **read-only** graph of the repo — files, symbols, imports, calls,
doc references, git sessions — under `.veridge/`, and serves **ranked, token-budgeted structure**
(never file contents). The core has **zero runtime dependencies**; multi-language symbols need the
`[treesitter]` extra, the MCP server needs `[mcp]`.

**Golden rules — never break these:**

1. **Never add `veridge` to the project's own dependencies** (`package.json`, `requirements`,
   `pyproject`). It is a per-machine dev tool, not a project dependency.
2. Veridge is **read-only on sources**. It writes **only** its own `.veridge/` directory, which
   **must be gitignored**. Do not commit `.veridge/`.
3. **Prefer Veridge's tools over re-reading/grepping** to orient — cheaper, and it is the shared
   map both agents use.
4. After code changes the index is **stale**. Rebuild (`veridge build .`) before trusting
   `impact`/`focus`; `health`/`gate` tells you if it is stale.
5. **Do not send anything outside the repo on your own** (open issues, push, post). Draft it and
   **ask the human to confirm**. (See §4.)

### MCP tool cheat-sheet

| Tool | Use it to |
|------|-----------|
| `project_map` | Orient: areas, layers, most-important files (PageRank). Load first. |
| `focus "<task>"` | Minimal relevant subgraph for a task/file/symbol, within a token budget. |
| `impact <file\|symbol>` | Blast-radius of a change (what depends on it). `dependencies=true` inverts. |
| `find` / `neighbors` | Locate a node by text; inspect a node's edges. |
| `why <a> <b>` / `tour` | Shortest typed path between two nodes; a reading tour of key files. |
| `health` | Anti-drift status: broken refs, stale files, orphans. |

CLI equivalents (outside MCP): `veridge build|stats|gate|map|focus|impact|why|tour|view`.
**If the MCP tools aren't available in your client, use the CLI — every tool has a CLI twin.**
Run **`veridge doctor`** to check setup here (index built? extras installed? MCP wired for
Claude *and* Codex?) — it prints the exact next command for anything missing.

---

## 1. Setup A — a NEW project/repo

Greenfield, or Veridge was never set up here.

1. **Install on this machine** (not in the project): `pip install "veridge[treesitter,mcp]"`;
   verify `veridge --version`.
2. **Build:** from the repo root, `veridge build .`. Confirm it finishes without errors and
   `veridge stats` looks proportionate to the code.
3. **Wire both assistants** (the team uses both):
   - `veridge integrate claude` → `.mcp.json` + a note in `CLAUDE.md`.
   - `veridge integrate codex` → `.codex/config.toml` + a note in `AGENTS.md`.
4. **Keep the index out of git:** ensure `.gitignore` contains `.veridge/` (add it once).
5. **Auto-freshness:** `veridge install-hook` (drops a `post-commit` rebuild hook).
6. **Commit the config** so collaborators inherit it: `.mcp.json`, `.codex/config.toml`,
   `CLAUDE.md`, `AGENTS.md`, `.gitignore`. **Never** commit `.veridge/`.
7. **Verify:** run `veridge doctor` — every line should be `[ok]` (index, extras, both assistants
   wired, index gitignored).

Report what you did and what the human must approve (e.g. trusting the project MCP server).

---

## 2. Setup B — an EXISTING, already-running project: **evaluate first, install only after**

Do **not** wire anything yet. First prove Veridge earns its place.

### Phase 1 — Evaluate (read-only, nothing committed)
1. Install Veridge on this machine (as in §1.1) if missing.
2. `veridge build .` — writes only `.veridge/` (you will delete it if you bail).
3. Inspect quality, and **separate Veridge false positives from real project issues**:
   - `veridge stats` — do symbol/import/call counts look proportionate?
   - `veridge gate` — broken references & drift. Which are genuine dead links (project) vs
     mis-parsed noise (Veridge bug)?
   - `veridge map` / `veridge tour` — does the structure match reality?
   - `veridge impact <a core file>` — is the blast radius right (especially across
     packages/modules)?
   - `veridge focus "<a real task>"` — is the returned slice the one you'd actually need?
4. Fill in the **evaluation report** (§4 template). **Stop and show it to the human.**

### Phase 2 — Decide & install (only if it proved valuable)
- **If yes:** do §1 steps 3–6, then prepare (for the human's confirmation) the feedback in §4.
- **If no:** delete `.veridge/`, report why, stop. No changes to the project.

---

## 3. Multi-agent use (Claude + Codex on the same repo)

- **One shared map.** Both assistants' MCP servers read the same deterministic
  `.veridge/graph.json`. Same code → same graph, so Claude and Codex see an identical structure.
- **Index is local & gitignored.** Each machine builds its own; never commit `.veridge/` — no
  merge conflicts, no stale shared state.
- **Coordinate through the graph and git, not assumptions.** Before editing: `focus "<task>"` for
  the slice. Before finishing: `impact --diff` for the blast radius of your change. Agents see
  each other's work through git (Veridge's *session* layer turns commits + the files they touched
  into graph edges) — so rebuild after pulling.
- **Stay fresh, don't trust a stale map.** If `health`/`gate` says stale, rebuild before relying
  on `impact`/`focus`. The post-commit hook keeps it fresh automatically.
- **Same etiquette both sides.** `CLAUDE.md` and `AGENTS.md` carry the same directives, so the two
  assistants behave consistently and hand off cleanly.

---

## 4. Feedback: stats / project errors / Veridge bugs / fixes

Veridge has **no telemetry and never phones home** (deterministic, local, zero-deps — by design).
"Sending data to Veridge" means: produce a structured report and route each part to the right
place. **You (the agent) must not submit anything externally on your own — draft it and ask the
human to confirm, or let the human submit.**

- **To the team (this project):** real broken refs, drift, dead docs, risky hub files surfaced by
  `impact`. These are findings about *your own* code — fix them in the project.
- **To Veridge** (<https://github.com/galimar/veridge/issues>): Veridge false positives, parsing
  gaps, a language/framework it mishandled, plus the coverage stats that help improve it, and any
  proposed fix.

### Evaluation report template

```
## Veridge evaluation — <repo> @ <commit> — veridge <version>
Profile:   <languages, ~N files, monorepo?, frameworks>
Coverage:  files=…  symbols=…  imports=…  calls=…  references=…
Resolved well:        <what looked right>
False positives:      <ref/edge Veridge got wrong> — why it's wrong   -> Veridge
Gaps (Veridge missed): <real edges absent>                            -> Veridge
Project issues found: <dead links, drift, risky hubs>                 -> our team
Proposed Veridge fix: <concrete change, if any>                       -> Veridge
Verdict:   install / don't install — because …
```

Keep the two audiences separate: don't file your repo's dead links as Veridge bugs, and don't bury
a real Veridge parsing bug inside a project to-do.
