"""Layer git history onto the graph: one ``session`` node per commit, ``touches`` to its files.

Read-only and best-effort — with no git repository, this is a no-op. Git is asked to leave
non-ASCII paths verbatim (``core.quotePath=false``) and its output is decoded as UTF-8
explicitly, so accented file names line up with the graph's node ids on every platform.
Parsing is split in two: :func:`_run_git` shells out, :func:`_commits` turns the log into plain
dicts, and :func:`add_sessions` only builds nodes/edges from them.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

from veridge.model import Edge, EdgeType, Graph, Kind, Node

# ASCII record / unit separators: safe field delimiters that never occur in real paths.
_REC, _FIELD = "\x1e", "\x1f"


def _run_git(root: Path, *args: str) -> str | None:
    """Run ``git`` in ``root`` and return stdout, or ``None`` if git is absent/fails."""
    if not (root / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotePath=false", "-C", str(root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def git_changed_files(root: str | os.PathLike[str], *, base: str = "HEAD") -> list[str]:
    """POSIX paths changed vs ``base`` (tracked working-tree changes); ``[]`` without git."""
    out = _run_git(Path(root), "diff", "--name-only", base)
    return [ln.strip() for ln in out.splitlines() if ln.strip()] if out else []


def _commits(root: Path, limit: int) -> Iterator[dict[str, object]]:
    """Yield ``{hash, subject, date, author, files}`` for recent commits."""
    fmt = _REC + _FIELD.join(("%h", "%s", "%aI", "%an"))
    out = _run_git(root, "log", f"-{max(1, limit)}", "--no-merges", "--name-only",
                   f"--pretty=format:{fmt}")
    if not out:
        return
    for record in out.split(_REC):
        record = record.strip("\n")
        if not record:
            continue
        header, _, body = record.partition("\n")
        fields = (header.split(_FIELD) + ["", "", "", ""])[:4]
        if not fields[0]:
            continue
        yield {
            "hash": fields[0], "subject": fields[1], "date": fields[2], "author": fields[3],
            "files": [ln.strip() for ln in body.splitlines() if ln.strip()],
        }


def add_sessions(graph: Graph, root: str | os.PathLike[str], *, limit: int = 40) -> None:
    """Add a ``session`` node per recent commit and ``touches`` edges to the files it changed."""
    node_ids = set(graph.nodes)
    for c in _commits(Path(root), limit):
        h, subject = c["hash"], c["subject"]
        date, author = c["date"], c["author"]
        nid = f"session:{h}"
        if nid not in graph.nodes:
            graph.add_node(Node(
                id=nid, kind=Kind.SESSION, label=f"{h} {subject}".strip()[:80],
                description=f"commit {h} by {author} {str(date)[:10]}".strip(),
                meta={"date": date, "author": author, "subject": subject}))
        for path in c["files"]:  # type: ignore[union-attr]
            if path in node_ids:
                graph.add_edge(Edge(nid, path, EdgeType.TOUCHES))
