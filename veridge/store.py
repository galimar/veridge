"""Read and write the derived store under ``<project>/.veridge/``.

Two artefacts live there — ``graph.json`` and ``manifest.json`` — both derived and always
regenerable; the store never stands in for the project's own files. Writes go through a temp
file in the same directory and an ``os.replace``, so a crash mid-write can never leave a
truncated ``graph.json`` behind. Loads are forgiving: a missing or corrupt file reads back as
``None`` so callers can rebuild instead of raising.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

STORE_DIRNAME = ".veridge"
_GRAPH = "graph.json"
_MANIFEST = "manifest.json"


def store_dir(root: str | os.PathLike[str]) -> Path:
    """The ``.veridge`` directory for ``root`` (created lazily by writers)."""
    return Path(root).resolve() / STORE_DIRNAME


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # NamedTemporaryFile keeps the partial write off `path` until the rename commits it.
    tmp = NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                             dir=path.parent, prefix=".tmp-", delete=False)
    try:
        with tmp as fh:
            fh.write(text)
        os.replace(tmp.name, path)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)
        raise


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(root: str | os.PathLike[str], graph, manifest: dict[str, str]) -> Path:
    """Write ``graph.json`` and ``manifest.json``; return the store directory."""
    d = store_dir(root)
    _write_atomic(d / _GRAPH, graph.to_json())
    _write_atomic(d / _MANIFEST,
                  json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return d


def load_graph(root: str | os.PathLike[str]):
    """Load the stored graph, or ``None`` if it is absent or unreadable."""
    from veridge.model import Graph
    data = _read_json(store_dir(root) / _GRAPH)
    if data is None:
        return None
    try:
        return Graph.from_dict(data)
    except (ValueError, KeyError, TypeError):
        return None


def load_manifest(root: str | os.PathLike[str]) -> dict[str, str] | None:
    """Load the stored manifest, or ``None`` if absent, unreadable, or not a mapping."""
    data = _read_json(store_dir(root) / _MANIFEST)
    return data if isinstance(data, dict) else None
