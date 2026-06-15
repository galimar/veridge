"""Pull references and decision ids out of documentation text.

Three kinds of reference, because real docs use all three:

* markdown links ``[label](target)``,
* wikilinks ``[[Name]]`` / ``[[Name|alias]]``, and
* **bare path mentions in prose** (``src/app.py`` written inside a sentence) — the part
  generic tools miss, and a big reason this exists for documentation.

Prose paths are found in two steps: a generic regex picks out *path-shaped tokens*, then a set
membership test on the file extension keeps only the plausible ones — so the list of known
extensions lives as data, not baked into the pattern. Every regex is length-bounded, so even a
pathological document can't trigger quadratic backtracking.
"""

from __future__ import annotations

import re

# A reference that looks like a URL is for the web, not a project file — skip it.
_URL = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:)?//|^mailto:", re.IGNORECASE)
_MD_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?[^)]*\)")
_WIKILINK = re.compile(r"\[\[([^\[\]\n]{1,300})\]\]")
# A path-shaped token: ``name.ext`` with the extension validated separately, below.
_PATH_TOKEN = re.compile(r"(?<![\w./\\-])([A-Za-z0-9_][\w\-./\\]*\.[A-Za-z0-9]{1,8})\b")
_DECISION = re.compile(r"\b(?:D-[A-Z]{1,8}-\d{1,5}|ADR-\d{1,5}|RFC-\d{1,5})\b")

_REF_EXTS = frozenset((
    "md markdown rst txt pdf html htm docx adoc "
    "py js ts tsx jsx mjs cjs go rs java c cc cpp h hpp rb php cs ps1 psm1 sh bash sql "
    "toml ini cfg conf yaml yml json jsonl xml csv tsv db sqlite duckdb parquet"
).split())


def _normalize(target: str) -> str:
    """Strip code-span backticks, drop any ``#anchor``/``?query``, and POSIX-ify separators."""
    t = target.strip().strip("`").strip()
    t = re.split(r"[#?]", t, maxsplit=1)[0]
    return t.replace("\\", "/").strip()


def _scan(text: str):
    """Yield raw ``(target, kind)`` in document order (links, then wikilinks, then paths)."""
    for m in _MD_LINK.finditer(text):
        yield m.group(1), "link"
    for m in _WIKILINK.finditer(text):
        name = m.group(1).split("|", 1)[0].split("#", 1)[0].strip()
        if name:
            yield name, "wikilink"
    for m in _PATH_TOKEN.finditer(text):
        token = m.group(1)
        if token.rsplit(".", 1)[-1].lower() in _REF_EXTS:
            yield token, "path"


def extract_references(text: str) -> list[tuple[str, str]]:
    """Return de-duplicated ``(target, kind)`` in first-seen order (URLs excluded).

    ``kind`` is ``"link"``, ``"wikilink"`` or ``"path"``. Links and wikilinks are intentional
    (an unresolved one may be flagged broken); a plain ``"path"`` is used only when it resolves.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw, kind in _scan(text):
        if _URL.match(raw.strip()):
            continue
        target = _normalize(raw)
        if target and target not in seen:
            seen.add(target)
            out.append((target, kind))
    return out


def extract_decisions(text: str) -> list[str]:
    """Return de-duplicated decision ids (``ADR-N`` / ``RFC-N`` / ``D-X-N``) in first-seen order."""
    return list(dict.fromkeys(m.group(0) for m in _DECISION.finditer(text)))
