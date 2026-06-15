"""Enumerate the indexable files under a project root (read-only, symlink-loop-safe)."""

from __future__ import annotations

import os
from pathlib import Path

from veridge.ignore import IgnoreRules


def iter_files(root: Path) -> list[str]:
    """Return the sorted POSIX relative paths of indexable files under ``root``.

    ``os.walk`` never follows directory symlinks, so cycles can't trap the walk; a path that
    won't express relative to ``root`` (an exotic junction) is skipped rather than fatal. The
    ignore rules are loaded once and reused for the whole walk.
    """
    rules = IgnoreRules.load(root)
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not rules.skip_dir(d)]
        here = Path(dirpath)
        for name in filenames:
            try:
                rel = (here / name).relative_to(root).as_posix()
            except ValueError:
                continue
            if not rules.skip_file(rel, name):
                found.append(rel)
    return sorted(found)
