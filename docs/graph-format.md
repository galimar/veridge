# The `graph.json` format

Veridge writes one artefact other tools can build on: `.veridge/graph.json`. It is a small,
deterministic, **versioned** JSON document — no contents of your files are ever copied into it,
only their structure and relationships. This page is the contract.

> Stability: the shape is versioned by the top-level `schema_version` (currently **1**). A
> breaking change bumps it; readers may check it and adapt or refuse. Within a version, fields
> may be *added* but not removed or repurposed.

## Top level

```json
{
  "schema_version": 1,
  "project": "myproject",
  "nodes": [ /* Node */ ],
  "edges": [ /* Edge */ ]
}
```

`nodes` and `edges` are sorted deterministically (nodes by `id`; edges by
`source, target, type`), so the same project always serialises byte-for-byte the same — clean
diffs, reproducible hashes.

## Node

```json
{
  "id": "src/util.py#greet",
  "kind": "symbol",
  "label": "greet",
  "path": "src/util.py",
  "category": null,
  "description": "function in src/util.py",
  "meta": { "line": 12, "symbol": "function" }
}
```

| field | meaning |
|---|---|
| `id` | stable, unique identifier (see **id conventions** below) |
| `kind` | one of `file`, `symbol`, `area`, `decision`, `session` |
| `label` | short human label (a file's basename, a symbol's qualified name, …) |
| `path` | POSIX path for `file`/`symbol` nodes; `null` otherwise |
| `category` | for `file` nodes only: `structure`, `doc`, `code`, `config`, `data`, `memory` (else `null`) |
| `description` | short generated, human-readable summary |
| `meta` | free-form extras (see below) |

**id conventions**

| kind | id |
|---|---|
| `file` | the POSIX path relative to the project root, e.g. `src/util.py` |
| `symbol` | `<file-id>#<qualname>`, e.g. `src/util.py#App.start` |
| `area` | `area:<name>`, where name is the top-level directory (or `(root)`) |
| `decision` | `decision:<id>`, e.g. `decision:ADR-7` |
| `session` | `session:<short-hash>`, e.g. `session:1a2b3c4` |

**common `meta` keys**

- file: `size` (bytes), `broken_refs` (list of unresolved intentional link targets)
- symbol: `line` (1-based), `symbol` (`function` | `class`)
- session: `date`, `author`, `subject`

## Edge

```json
{ "source": "src/app.py#run", "target": "src/util.py#greet", "type": "calls", "meta": {} }
```

`type` is one of:

| type | from → to | meaning |
|---|---|---|
| `defines` | file → symbol | the file declares the symbol |
| `imports` | code → code | a file-level import/use |
| `calls` | symbol → symbol | a resolved call within the project |
| `references` | doc → file | a markdown link, wikilink, or prose path mention |
| `belongs_to` | node → area | area membership |
| `mentions` | doc → decision | a document cites a decision id |
| `touches` | session → file | a commit changed the file |

Edges are directed (`source` → `target`) and de-duplicated by `(source, target, type)`.

## Exporting

`graph.json` is the canonical form. For consumption elsewhere:

```bash
veridge export . --format native      # this schema (graph.json), to stdout
veridge export . --format jgf         # JSON Graph Format (generic, tool-friendly)
veridge export . --format dot         # Graphviz DOT (for rendering)
veridge export . --format jgf --out graph.jgf.json
```

The **JGF** export wraps the same nodes/edges in the widely understood
[JSON Graph Format](https://jsongraphformat.info/) shape — a directed graph with node
`metadata` and edge `relation` — so an agent, a notebook, a visualiser, or an LLM-comprehension
tool can read Veridge's structural layer without knowing its internals.
