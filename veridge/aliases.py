"""Resolve non-relative JS/TS/Vue import aliases to project paths.

Front-end projects rarely import only with ``./``: they use aliases like ``@/components/Foo`` or
``~/utils`` configured in ``tsconfig.json`` / ``jsconfig.json`` (``compilerOptions.paths``) or by
Vite/Nuxt convention. This reads those rules so the import resolver can turn an alias into a real
file. Config is read forgivingly (JSONC: comments and trailing commas are tolerated).
"""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path


def _read_jsonc(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)   # block comments
    text = re.sub(r"(?m)//.*$", "", text)                    # line comments
    text = re.sub(r",(\s*[}\]])", r"\1", text)               # trailing commas
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def load_aliases(root: Path) -> list[tuple[str, str]]:
    """Return ``[(prefix, target_dir)]`` alias rules for the project, longest prefix first.

    A rule like ``("@/", "src")`` means an import starting ``@/`` maps under ``src/``.
    """
    cfg = _read_jsonc(root / "tsconfig.json") or _read_jsonc(root / "jsconfig.json") or {}
    co = cfg.get("compilerOptions")
    co = co if isinstance(co, dict) else {}
    base = co.get("baseUrl") if isinstance(co.get("baseUrl"), str) else "."
    paths = co.get("paths") if isinstance(co.get("paths"), dict) else {}

    rules: list[tuple[str, str]] = []
    for pattern, targets in paths.items():
        if not (isinstance(targets, list) and targets and isinstance(targets[0], str)):
            continue
        target = targets[0]
        if pattern.endswith("/*") and target.endswith("/*"):
            rules.append((pattern[:-1], posixpath.normpath(posixpath.join(base, target[:-1]))))
        elif "*" not in pattern and "*" not in target:
            rules.append((pattern, posixpath.normpath(posixpath.join(base, target))))

    # Conservative defaults for the ubiquitous Vite/Nuxt aliases — only if a `src/` exists.
    if (root / "src").is_dir():
        for pre in ("@/", "~/"):
            if not any(p == pre for p, _ in rules):
                rules.append((pre, "src"))

    rules.sort(key=lambda r: -len(r[0]))     # longest, most specific prefix wins
    return rules
