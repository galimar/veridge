from __future__ import annotations

import pytest

from veridge import store
from veridge import watch as watcher
from veridge.freshness import index


def test_refresh_no_change_is_noop(project):
    g, m = index(project)
    store.save(project, g, m)
    assert watcher.refresh_if_changed(project) is None


def test_refresh_no_baseline_builds(project):
    diff = watcher.refresh_if_changed(project)          # no store yet
    assert diff is not None and diff["added"]
    assert store.load_graph(project) is not None


def test_refresh_detects_and_rebuilds(project):
    g, m = index(project)
    store.save(project, g, m)
    (project / "extra.md").write_text("hello, see src/util.py\n", encoding="utf-8")
    diff = watcher.refresh_if_changed(project)
    assert diff is not None
    assert "extra.md" in diff["added"]
    # the rebuilt+saved graph now contains the new file...
    assert "extra.md" in store.load_graph(project).nodes
    # ...and a second pass sees no change.
    assert watcher.refresh_if_changed(project) is None


def test_install_hook(project):
    (project / ".git").mkdir(exist_ok=True)
    hook = watcher.install_post_commit_hook(project)
    assert hook.is_file()
    body = hook.read_text(encoding="utf-8")
    assert "veridge build" in body
    # idempotent: re-installing our own hook is fine
    watcher.install_post_commit_hook(project)


def test_install_hook_refuses_foreign(project):
    (project / ".git" / "hooks").mkdir(parents=True, exist_ok=True)
    (project / ".git" / "hooks" / "post-commit").write_text(
        "#!/bin/sh\necho someone-elses-hook\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        watcher.install_post_commit_hook(project)


def test_install_hook_requires_git(tmp_path):
    with pytest.raises(FileNotFoundError):
        watcher.install_post_commit_hook(tmp_path)
