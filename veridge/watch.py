"""Keep the map fresh automatically: a poll-based watcher and a git post-commit hook.

Both rest on the content-hash manifest. ``refresh_if_changed`` rebuilds **only when the tree
actually changed** (an empty manifest diff is a no-op), so an idle watcher costs nothing but a
``stat`` of each file. The rebuild itself is a *full* (but fast) re-index — correct by
construction, since cross-file edges and the resolution indexes depend on the whole file set;
incremental graph patching is a future optimisation, not a correctness shortcut.

No third-party dependency: the watcher polls with ``time.sleep`` over the stdlib manifest.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from veridge import store
from veridge.freshness import build_manifest, diff_manifest, index

_HOOK_MARKER = "# veridge: keep the map fresh"


def refresh_if_changed(root: str | os.PathLike[str]) -> dict[str, list[str]] | None:
    """Rebuild + save the graph iff the tree changed since the stored manifest.

    Returns the ``{added, removed, changed}`` diff when a rebuild happened, else ``None``.
    With no stored baseline, builds fresh and reports every file as added.
    """
    old = store.load_manifest(root)
    if old is None:
        graph, manifest = index(root)
        store.save(root, graph, manifest)
        return {"added": sorted(manifest), "removed": [], "changed": []}
    diff = diff_manifest(old, build_manifest(root))
    if diff["added"] or diff["removed"] or diff["changed"]:
        graph, manifest = index(root)
        store.save(root, graph, manifest)
        return diff
    return None


def watch(root: str | os.PathLike[str], *, interval: float = 2.0,
          on_change: Callable[[dict[str, list[str]]], None] | None = None) -> None:
    """Poll ``root`` every ``interval`` seconds, rebuilding when it changes.

    Blocks until interrupted (``KeyboardInterrupt``). ``on_change`` is called with the diff
    after each rebuild. The initial call brings the store up to date before looping.
    """
    diff = refresh_if_changed(root)
    if diff and on_change:
        on_change(diff)
    while True:
        time.sleep(max(0.2, interval))
        diff = refresh_if_changed(root)
        if diff and on_change:
            on_change(diff)


def install_post_commit_hook(root: str | os.PathLike[str]) -> Path:
    """Install a ``.git/hooks/post-commit`` hook that runs ``veridge build`` after each commit.

    Raises ``FileNotFoundError`` if ``root`` is not a git repository, and ``FileExistsError``
    if a foreign post-commit hook is already present (we never clobber someone else's hook).
    Re-running is idempotent when the existing hook is ours.
    """
    root_p = Path(root)
    if not (root_p / ".git").is_dir():
        raise FileNotFoundError(f"not a git repository: {root_p.resolve()}")
    hooks = root_p / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "post-commit"
    if hook.exists() and _HOOK_MARKER not in hook.read_text(encoding="utf-8", errors="ignore"):
        raise FileExistsError(
            f"a post-commit hook already exists at {hook}; not overwriting it")
    hook.write_text(
        "#!/bin/sh\n" + _HOOK_MARKER + "\nveridge build . >/dev/null 2>&1 || true\n",
        encoding="utf-8", newline="\n")
    try:
        os.chmod(hook, 0o755)
    except OSError:
        pass  # not applicable on Windows; git runs the hook regardless
    return hook
