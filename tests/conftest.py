"""Shared fixtures: a small synthetic project written into a temp dir, plus its graph."""

from __future__ import annotations

from pathlib import Path

import pytest

from veridge.freshness import index

_FILES = {
    "README.md": (
        "# Demo\n\nThe entry point is `src/app.py`, which uses [util](src/util.py).\n"
        "A dead link: [gone](src/missing.py).\n"
        "See [[Missing Doc]] too.\nDecision ADR-7 applies here.\n"
    ),
    "src/__init__.py": "",
    "src/app.py": (
        "from src.util import greet\n\n"
        "def run():\n    return greet('world')\n\n"
        "class App:\n    def start(self):\n        return run()\n"
    ),
    "src/util.py": "def greet(name):\n    return f'hi {name}'\n",
    "docs/guide.md": "Guide. Implements ADR-7. Mentions src/util.py in prose.\n",
    "data/big.csv": "a,b,c\n1,2,3\n",
    "config.toml": "[tool]\nx = 1\n",
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for rel, content in _FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture
def graph(project: Path):
    g, _ = index(project)
    return g
