"""Veridge — the always-fresh, low-token map of a whole project.

Veridge indexes a project read-only into a typed graph that unifies four layers most
tools keep apart:

* **documents** (with references — including plain path mentions written in prose),
* **code** down to the *symbol* (functions/classes), via pluggable parsers,
* **decisions** (ADR / RFC / D-XXX ids found in docs), and
* **sessions** (git commits and the files they touched).

It then *ranks* the graph with PageRank, so queries can return the **minimal relevant
subgraph within a token budget** — the cheap, accurate context an AI assistant needs to
orient itself, and a map a human can read. The core has zero runtime dependencies.
"""

from __future__ import annotations

__version__ = "0.7.2"

__all__ = ["__version__"]
