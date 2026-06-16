"""Freshness signatures, the one-walk ``index`` entry point, and the anti-drift gate.

A *manifest* is a ``{path: signature}`` map. Two signature flavours:

* ``c:<digest>`` — for source/doc text small enough to hold in memory, a content digest taken
  over **newline-normalised** bytes, so a CRLF↔LF flip on checkout is not seen as a change;
* ``d:<size>-<mtime>`` — for data, binaries and large files, a cheap stat signature with no
  bytes read, keeping indexing light on data-heavy projects.

Diffing the stored manifest against a fresh one tells the gate whether the map is still in
sync; the gate also reports broken references and orphan files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import blake2b
from os import PathLike
from os.path import splitext
from pathlib import Path

from veridge.indexer import build_graph
from veridge.model import Graph
from veridge.walk import iter_files

# Text whose content we digest (cheap to hold whole); everything else gets a stat signature.
_HASH_CAP = 1_000_000
_TEXT_EXTS = frozenset({
    ".md", ".markdown", ".rst", ".txt", ".adoc", ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs",
    ".cjs", ".vue", ".toml", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".html", ".htm", ".css",
    ".sql", ".ps1", ".psm1", ".sh", ".bash", ".go", ".rs", ".java", ".c", ".cc", ".cpp", ".h",
    ".hpp", ".rb", ".php", ".cs",
})

Manifest = dict[str, str]


def _content_digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return blake2b(raw, digest_size=12).hexdigest()


def _signature(root: Path, rel: str) -> str | None:
    """A freshness signature for one file, or ``None`` if it can't be stat'd."""
    p = root / rel
    try:
        st = p.stat()
    except OSError:
        return None
    if splitext(rel)[1].lower() in _TEXT_EXTS and st.st_size <= _HASH_CAP:
        try:
            return "c:" + _content_digest(p)
        except OSError:
            return None
    # Nanosecond mtime: a same-size edit within the same second still registers as a change.
    return f"d:{st.st_size}-{st.st_mtime_ns}"


def build_manifest(root: str | PathLike[str]) -> Manifest:
    """Return ``{relative_path: signature}`` for every indexable file under ``root``."""
    base = Path(root).resolve()
    return {rel: sig for rel in iter_files(base) if (sig := _signature(base, rel)) is not None}


def index(root: str | PathLike[str]) -> tuple[Graph, Manifest]:
    """Build the graph and the manifest from a single directory walk."""
    base = Path(root).resolve()
    rels = iter_files(base)
    graph = build_graph(base, _rels=rels)
    manifest = {rel: sig for rel in rels if (sig := _signature(base, rel)) is not None}
    return graph, manifest


def diff_manifest(old: Manifest, new: Manifest) -> dict[str, list[str]]:
    """Return ``{added, removed, changed}`` (sorted) between two manifests."""
    before, after = set(old), set(new)
    return {
        "added": sorted(after - before),
        "removed": sorted(before - after),
        "changed": sorted(p for p in before & after if old[p] != new[p]),
    }


# -- the anti-drift gate ----------------------------------------------------
@dataclass
class GateReport:
    broken: list[tuple[str, str]] = field(default_factory=list)
    stale: dict[str, list[str]] = field(
        default_factory=lambda: {"added": [], "removed": [], "changed": []})
    orphans: list[str] = field(default_factory=list)

    @property
    def stale_count(self) -> int:
        return sum(len(v) for v in self.stale.values())

    @property
    def ok(self) -> bool:
        """Green only when nothing must be fixed (no broken refs, no stale files)."""
        return not self.broken and self.stale_count == 0

    def summary(self) -> str:
        added, removed, changed = (self.stale[k] for k in ("added", "removed", "changed"))
        lines = [
            f"broken references: {len(self.broken)}",
            f"stale files: {self.stale_count} "
            f"(+{len(added)} / -{len(removed)} / ~{len(changed)})",
            f"orphans: {len(self.orphans)} (info)",
            *(f"  [broken] {src} -> {tgt}" for src, tgt in self.broken[:20]),
        ]
        return "\n".join(lines)


def find_broken(graph: Graph) -> list[tuple[str, str]]:
    """Every (source, target) where a doc intentionally links a missing project file."""
    return sorted(
        (n.id, target)
        for n in graph.nodes.values()
        for target in n.meta.get("broken_refs", [])
    )


def find_orphans(graph: Graph) -> list[str]:
    """File nodes wired to nothing but their area — the digest uses the same predicate."""
    return sorted(n.id for n in graph.nodes.values() if graph.is_orphan(n.id))


def evaluate(graph: Graph, old_manifest: Manifest | None,
             new_manifest: Manifest) -> GateReport:
    """Build a :class:`GateReport`; ``old_manifest is None`` means "no baseline" → not stale."""
    empty: dict[str, list[str]] = {"added": [], "removed": [], "changed": []}
    stale = diff_manifest(old_manifest, new_manifest) if old_manifest is not None else empty
    return GateReport(broken=find_broken(graph), stale=stale, orphans=find_orphans(graph))
