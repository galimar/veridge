"""Assign every file a :class:`~veridge.model.Category` from its path alone.

The mapping is **table-driven**: a file's category is decided by consulting, in order, a few
cheap signals — a memory marker in the path, a precomputed *extension → category* table, a set
of well-known file names, and finally a documents-vs-config fallback. Keying on widely shared
conventions (not a project-specific vocabulary) means it works out of the box on any repo and
stays easy to tune: add an extension to a tuple, or a name to a set.
"""

from __future__ import annotations

from os.path import splitext

from veridge.model import Category

# One extension → category table, assembled once from per-category tuples. A lookup here is
# the primary signal; documents are handled by the fallback so prose keeps a single home.
_EXTS: dict[Category, tuple[str, ...]] = {
    Category.CODE: (
        ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".vue", ".go", ".rs", ".java",
        ".kt", ".c", ".cc", ".cpp", ".h", ".hpp", ".rb", ".php", ".cs", ".swift", ".scala",
        ".lua", ".ps1", ".psm1", ".sh", ".bash", ".sql",
    ),
    Category.DATA: (
        ".db", ".sqlite", ".sqlite3", ".duckdb", ".parquet", ".csv", ".tsv", ".jsonl", ".ndjson",
    ),
    Category.CONFIG: (
        ".toml", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".env", ".json", ".xml", ".properties",
    ),
}
_EXT_CATEGORY: dict[str, Category] = {ext: cat for cat, exts in _EXTS.items() for ext in exts}

_DOC_EXTS = frozenset({
    ".md", ".markdown", ".rst", ".txt", ".pdf", ".html", ".htm", ".docx", ".adoc",
})

# File names that override the extension table (foundation docs, and config-by-name).
_STRUCTURE_NAMES = frozenset({
    "readme", "readme.md", "readme.rst", "index.md", "architecture.md", "changelog.md",
    "contributing.md", "license", "license.md", "authors", "notice",
})
_CONFIG_NAMES = frozenset({
    ".gitignore", ".veridgeignore", "dockerfile", "makefile", "caddyfile", ".editorconfig",
})


def classify(rel_posix: str) -> Category:
    """Return the :class:`Category` for the file at POSIX relative path ``rel_posix``."""
    name = rel_posix.rsplit("/", 1)[-1].lower()
    ext = splitext(name)[1]

    # 1. A `memory/` directory or `memory.*` file is persistent memory, whatever its extension.
    if name.startswith("memory.") or "memory" in rel_posix.lower().split("/"):
        return Category.MEMORY

    # 2. Code and data are unambiguous from their extension — decide immediately.
    by_ext = _EXT_CATEGORY.get(ext)
    if by_ext in (Category.CODE, Category.DATA):
        return by_ext

    # 3. Well-known names beat the remaining signals (a README is structure, not just a doc).
    if name in _STRUCTURE_NAMES:
        return Category.STRUCTURE
    if name in _CONFIG_NAMES or by_ext is Category.CONFIG:
        return Category.CONFIG

    # 4. Anything document-shaped (or extensionless prose) is a document; else treat as config.
    return Category.DOC if (ext in _DOC_EXTS or ext == "") else Category.CONFIG
