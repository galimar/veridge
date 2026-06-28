"""Enumerate the indexable files under a project root (read-only, symlink-loop-safe).

In a **git repository** the file set comes from git itself (`git ls-files`), so Veridge honours
exactly what git ignores — `.gitignore` (including nested ones), `.git/info/exclude`, and the
user's global excludes — with no pattern parsing of our own. Veridge's built-in skips (vendor
dirs, binaries, lockfiles) and an optional ``.veridgeignore`` still apply on top. Outside a git
repo (or if git is unavailable) it falls back to a plain filesystem walk with the same skips.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from veridge.ignore import IgnoreRules


def _git_ls_files(root: Path) -> list[str] | None:
    """Posix-relative paths git would show (tracked + untracked-not-ignored), honouring
    ``.gitignore``. ``None`` when ``root`` isn't a git repo or git can't be run."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others",
             "--exclude-standard", "-z"],
            capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [p for p in proc.stdout.split("\0") if p]


def _skip_rel(rel: str, rules: IgnoreRules) -> bool:
    """Veridge's own skips for a relative path (a parent dir is vendored, or the file is noise)."""
    parts = rel.split("/")
    return any(rules.skip_dir(p) for p in parts[:-1]) or rules.skip_file(rel, parts[-1])


def _walk_fs(root: Path, rules: IgnoreRules) -> list[str]:
    """Plain filesystem walk (the fallback when there's no git). ``os.walk`` never follows
    directory symlinks, so cycles can't trap it; a path that won't express relative to ``root``
    (an exotic junction) is skipped rather than fatal."""
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
    return found


def iter_files(root: Path) -> list[str]:
    """Return the sorted POSIX relative paths of indexable files under ``root``.

    Honours ``.gitignore`` in a git repo (via git), then applies Veridge's built-in skips and
    ``.veridgeignore`` on top; falls back to a filesystem walk outside git.
    """
    rules = IgnoreRules.load(root)
    git_files = _git_ls_files(root)
    if git_files is not None:
        found = [rel for rel in git_files
                 if not _skip_rel(rel, rules) and (root / rel).is_file()]
    else:
        found = _walk_fs(root, rules)
    return sorted(found)
