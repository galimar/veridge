<!-- Thanks for contributing to Veridge! Keep the diff focused. -->

## What & why

<!-- What does this change, and why? Link any related issue. -->

## Checklist

- [ ] `ruff check veridge tests` passes
- [ ] `pytest -q` passes (added/updated tests for behaviour changes)
- [ ] Keeps the design principles intact: **read-only · zero-deps core · low-token · ranked ·
      deterministic** (new dependencies go behind an optional extra, never in the core)
