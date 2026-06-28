from __future__ import annotations

import subprocess

import pytest

from veridge.walk import iter_files


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_iter_files_honours_gitignore(tmp_path):
    try:
        _git(tmp_path, "init")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "secret.env").write_text("KEY=1\n", encoding="utf-8")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "g.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("secret.env\nout/\n", encoding="utf-8")

    files = iter_files(tmp_path)
    assert "app.py" in files
    assert "secret.env" not in files                       # gitignored file
    assert not any(f.startswith("out/") for f in files)    # gitignored directory


def test_iter_files_indexes_tracked_file_even_if_pattern_would_ignore(tmp_path):
    try:
        _git(tmp_path, "init")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    (tmp_path / "keep.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "keep.py")                       # tracked
    (tmp_path / ".gitignore").write_text("*.py\n", encoding="utf-8")  # would ignore it if untracked
    files = iter_files(tmp_path)
    assert "keep.py" in files                              # tracked wins, git lists it


def test_iter_files_without_git_walks_fs(tmp_path):
    # no git repo -> filesystem walk; the built-in vendor-dir skip still applies
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("//\n", encoding="utf-8")
    files = iter_files(tmp_path)
    assert "app.py" in files
    assert not any("node_modules" in f for f in files)
