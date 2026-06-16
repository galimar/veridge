# Veridge — Roadmap

This roadmap is organised by **phases**, each shippable on its own. The guiding rule never
changes: **everything the core does stays deterministic, read-only, low-token and zero-deps —
no LLM ever builds the graph.** (The functional roadmap, Phases 0–5, is shipped; see the status
note at the bottom.)

Positioning we are steering toward:

> *Everything Veridge does is **deterministic and free**: it builds the graph without an LLM,
> and hands an agent the right context within a token budget. Semantics are an optional extra,
> not a prerequisite.*

Legend — effort: **S** ≈ ½–1 day · **M** ≈ 2–4 days · **L** ≈ 1–2 weeks. Status: ☑ done ·
◐ in progress · ☐ planned.

---

## Phase 0 — Core engine ☑ (v0.1, shipped)

The unified, indexed graph (files + Python symbols + areas + decisions + git sessions),
`ast`-based symbol/import/**call** extraction, doc references incl. prose path mentions,
global + personalised **PageRank**, token budgeting, the `veridge focus` signature query, the
anti-drift gate, the CLI and the optional MCP server. 43 tests, ruff clean.

Foundations the rest of the roadmap builds on: [`model.py`](veridge/model.py) (indexed
adjacency), [`rank.py`](veridge/rank.py) (PageRank + RWR), [`query.py`](veridge/query.py)
(`focus`/budget), [`indexer.py`](veridge/indexer.py) (the call graph).

---

## Phase 1 — `veridge impact`: deterministic blast-radius ☑ **(shipped)** · **M**

**Delivered:** [`impact.py`](veridge/impact.py) (granularity-bridging reverse/forward
reachability), `query.impact` (proximity-weighted personalised-PageRank ranking + token
budget), `veridge impact <seed|--diff> [--deps] [--hops] [--budget] [--json]`, the `git diff`
seed helper in [`sessions.py`](veridge/sessions.py), an MCP `impact` tool, and 9 dedicated
tests. Original design below.

---


**The differentiator.** "If I change X, what is affected — and what's the minimal context to
review it safely?" Answered for free from the call/import/reference graph we already have —
pure graph work, no model.

**Why it's ours to win:** the graph is already directed and typed. Impact is *reverse
reachability* over the right edge types — no model, no cost, exact and reproducible.

**Design (grounded in current code):**
- New module `impact.py`. Treat `imports`/`calls`/`references`/`defines` as the propagation
  edges (configurable); ignore `belongs_to`.
- `dependents(graph, seed, hops=None)` — reverse BFS over `in_edges` (who depends on the seed):
  the blast radius. `dependencies(graph, seed)` — forward BFS (what the seed needs).
- Lift a file seed to its symbols and a symbol seed to its file, so `veridge impact src/util.py`
  and `veridge impact greet` both work.
- **Budgeted variant:** rank the impacted set with a personalised PageRank seeded on the
  *impacted nodes* (reuse `rank.pagerank(seeds=…)`), then `select_within_budget` — so a huge
  blast radius still returns the *most important* affected nodes within a token budget.
- **Diff mode:** `veridge impact --diff` reads `git diff --name-only` (reuse the subprocess
  pattern in [`sessions.py`](veridge/sessions.py)) and seeds from the changed files →
  "blast-radius of my working changes", the agent-facing killer use case.

**Deliverables:** `impact.py`; `query.impact(...)`; `veridge impact <seed|--diff> [--budget] [--hops] [--json]`;
MCP tool `impact`; tests (reverse reachability correctness, file↔symbol lifting, budget cap,
diff seeding); README section.

**Risks:** over-broad radius on hub nodes → mitigated by the budgeted ranking + a `--hops` cap.

---

## Phase 2 — Deterministic comprehension (built without an LLM) ☑ **(shipped)** · **M**

Several "teaching" features, reached from our graph for free — no model.

- **2a · Architectural layers in `map`.** ☑ [`layers.py`](veridge/layers.py): heuristic grouping
  (entrypoint / api / service / core / data / ui / util / tests / config / docs) from path
  segments, category and filename; `by_layer` block in `query.project_map`, line in `veridge map`.
- **2b · `veridge tour`.** ☑ `query.tour`: top-N PageRank files ordered by Kahn's algorithm on the
  collapsed file-level dependency graph (dependencies first; ties/cycles broken by PageRank),
  emitted as a compact, budgeted walkthrough with per-stop `uses`/`used_by`.
- **2c · `veridge why <a> <b>`.** ☑ `query.why`: shortest typed path via BFS over the adjacency
  index, returned as an edge-annotated, direction-aware chain.

**Delivered:** [`layers.py`](veridge/layers.py), `query.why`/`query.tour`, CLI `why`/`tour`
+ `map` layers, MCP `why`/`tour` tools, JSON on all, tests, README. 67 tests pass, ruff clean.

---

## Phase 3 — Multi-language symbols via the `[treesitter]` extra ☑ **(shipped)** · **L**

Adds symbol-level parsing beyond Python, **without** touching the zero-deps core.

**Delivered:** [`treesitter.py`](veridge/treesitter.py) extracts symbols + a within-file call
graph for **JavaScript, TypeScript, Go, Rust, Java, PHP and Vue SFCs**, behind the optional `[treesitter]`
extra (`tree-sitter-language-pack`). Its `Symbol` output matches `parse_python`'s, so the
indexer funnels every language through one `_add_symbols` path — ranking, budget, `impact`,
`tour` and `why` needed **zero changes** and now span languages. The accessors tolerate both
tree-sitter binding shapes (property- and method-style nodes), so the extra survives binding
upgrades; with the extra absent, `extract_symbols` returns `None` and those files degrade to
file-level info. 8 tests behind `pytest.importorskip`. 75 tests pass, ruff clean; verified
end-to-end on a mixed JS+Go project.

**Framework wiring (added):** [`laravel.py`](veridge/laravel.py) recognises the convention-based
links a pure call graph misses — route files → their controllers and the `EventServiceProvider`'s
events → their listeners (resolved by `X::class` name to classes already in the graph, emitted as
`references` edges, so `impact`/`focus` follow them). JS/TS/Vue import resolution now also handles
**path aliases** (`@/…`, `~`, `tsconfig`/`jsconfig` `paths`). All deterministic, regex/AST-based,
no runtime introspection.

**Follow-up (not blocking):** cross-file *import* resolution for Go/Rust/Java (today they get
symbols + calls; JS/TS/Python also get import edges).

---

## Phase 4 — Human viewer ☑ **(shipped)** · **M**

The human-facing pillar — an **offline, self-contained** HTML graph.

**Delivered:** [`viewer.py`](veridge/viewer.py) + [`ui/template.html`](veridge/ui/template.html):
a single `.veridge/view.html` with the data inlined and a **hand-written vanilla-JS canvas
force-directed renderer** — **no CDN, no bundled library, no server** (zero deps in the UI too).
Nodes coloured by kind, a toggleable legend, search, drag/zoom/pan, and a click-through detail
panel. `veridge view --focus "<q>"` renders exactly the `focus` subgraph, so a human sees the
slice the agent works from. XSS-safe inlining (every `<` escaped in the JSON payload); large
graphs auto-reduce to the PageRank backbone (`query.backbone` / `query.induced_subgraph`).
6 tests; 81 pass, ruff clean.

---

## Phase 5 — Live freshness (watch-mode) ☑ **(shipped)** · **S–M**

Turns the anti-drift gate from a manual check into something that stays green by itself.

**Delivered:** [`watch.py`](veridge/watch.py) — `refresh_if_changed` rebuilds **only when the
content-hash manifest actually changed** (an idle watcher just `stat`s each file); `veridge
watch` polls on an interval (stdlib `time.sleep`, no `watchdog` dep); `veridge install-hook`
drops a `post-commit` git hook running `veridge build` (refuses to clobber a foreign hook;
idempotent for ours). 6 tests; 87 pass, ruff clean.

**Follow-up (not blocking):** *incremental* rebuild — re-index only the changed files and patch
their nodes/edges. The current rebuild is full but fast, and **correct by construction** (cross-
file edges and the resolution indexes depend on the whole file set), so incremental is a pure
optimisation, never a correctness shortcut.

---

## Phase 6 — Optional semantic enrichment: `veridge enrich` ☒ **(declined)** · *out of scope*

Considered and **deliberately not built.** It would have been the only place an LLM entered the
pipeline — and even behind an opt-in extra, it blurs the one thing that makes Veridge distinct:
*everything is deterministic, free and built without a model*. With no demonstrated demand, a
speculative LLM layer trades the project's identity for capability that lives elsewhere. The
door stays closed unless real users ask for it; if reopened, it would remain opt-in, off by
default, cached and budget-capped, with the core untouched.

---

## Phase 7 — Release & governance ☑ **(shipped)** · **S**

CI (ruff + pytest on Python 3.10–3.13, with and without the `[treesitter]` extra), `CONTRIBUTING`
/ `SECURITY`, issue & PR templates, `py.typed`, and PyPI publishing via **Trusted Publishing**
(`release.yml`, no stored token). Published as `veridge` (name verified free before tagging).

---

## Status: the functional roadmap is complete

Phases 0–5 are shipped; Phase 6 is declined by design; Phase 7 is done. Veridge is a complete,
tested, published alpha. What remains is **backlog, not a committed plan** — pulled in only if a
real need appears:

- **Cross-file import edges for Go/Rust/Java** (today: symbols + calls; imports for Python/JS/TS).
- **Incremental rebuild** in watch-mode (today: full but fast, and correct by construction).
- Larger-graph viewer performance (the force layout is O(n²); backbone mode already caps it).

**North star (unchanged):** every feature here is something an agent or a human gets *for free
and reproducibly*, from the graph alone.
