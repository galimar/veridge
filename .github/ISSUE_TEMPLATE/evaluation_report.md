---
name: Evaluation report
about: Share how Veridge performed on a real project — coverage stats, false positives, gaps, fixes
labels: evaluation
---

<!--
For evaluating Veridge on a real repo (see docs/AGENT_PLAYBOOK.md §2 and §4). Report only what
concerns Veridge — coverage, false positives, parsing gaps, proposed fixes. Keep your project's own
dead links / drift out of this; those are issues in your repo, not in Veridge.
-->

**Project profile**
<!-- languages, ~N files, monorepo?, frameworks (e.g. Laravel + React + Vue) -->

**Coverage** (from `veridge stats`)
```
files=…  symbols=…  imports=…  calls=…  references=…
```

**Resolved well**
<!-- What Veridge got right. -->

**False positives (Veridge got it wrong)**
<!-- References/edges/broken-refs that are wrong, and WHY they're wrong. -->

**Gaps (real edges Veridge missed)**
<!-- Imports/calls/refs that exist in the code but aren't in the graph. -->

**Proposed fix (optional)**
<!-- A concrete change, if you have one. -->

**Environment**
- Veridge version: <!-- `veridge --version` -->
- Extras installed: <!-- [treesitter], [mcp] -->
- OS / Python:
