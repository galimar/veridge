"""Decide what the walker skips, bundled into one loaded-once :class:`IgnoreRules`.

Three built-in layers — derived/vendor *directories*, exact noise *file names*, and binary
*extensions* — plus any user globs from a ``.veridgeignore`` at the project root (one pattern
per line, ``#`` comments allowed). Globs match the POSIX relative path **case-sensitively**, so
the same ignore file selects the same files on Windows and POSIX alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from os.path import splitext
from pathlib import Path

IGNORE_FILE = ".veridgeignore"

_DIRS = frozenset({
    ".git", ".hg", ".svn", ".veridge",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".cache",
    ".venv", "venv", "env", "node_modules", "site-packages",
    "dist", "build", ".eggs", ".tox", ".next", ".nuxt", "target",
    ".idea", ".vscode",
})
_FILES = frozenset({
    ".DS_Store", "Thumbs.db", IGNORE_FILE,
    "package-lock.json", "poetry.lock", "yarn.lock", "pnpm-lock.yaml",
})
_EXTS = frozenset({
    ".pyc", ".pyo", ".pyd",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".gz", ".tar", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a",
    ".lock",
})


@dataclass(frozen=True)
class IgnoreRules:
    """The skip rules for one project: the built-in layers plus user globs."""

    globs: tuple[str, ...] = ()

    @classmethod
    def load(cls, root: Path) -> IgnoreRules:
        """Read ``.veridgeignore`` from ``root`` (absent file → no extra globs)."""
        f = root / IGNORE_FILE
        if not f.is_file():
            return cls()
        globs = tuple(
            line for raw in f.read_text(encoding="utf-8", errors="ignore").splitlines()
            if (line := raw.strip()) and not line.startswith("#")
        )
        return cls(globs)

    def skip_dir(self, name: str) -> bool:
        """True if a directory ``name`` should never be descended into."""
        return name in _DIRS or name.endswith(".egg-info")

    def skip_file(self, rel_posix: str, name: str) -> bool:
        """True if the file at ``rel_posix`` (basename ``name``) should be left out."""
        if name in _FILES or splitext(name)[1].lower() in _EXTS:
            return True
        return any(fnmatchcase(rel_posix, g) or fnmatchcase(name, g) for g in self.globs)
