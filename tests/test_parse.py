from __future__ import annotations

from veridge.parse_docs import extract_decisions, extract_references
from veridge.parse_python import parse_python


def test_python_symbols_and_methods():
    src = "def foo():\n    pass\n\nclass Bar:\n    def baz(self):\n        return foo()\n"
    mod = parse_python(src)
    quals = {s.qualname for s in mod.symbols}
    assert quals == {"foo", "Bar", "Bar.baz"}
    baz = next(s for s in mod.symbols if s.qualname == "Bar.baz")
    assert "foo" in baz.calls


def test_python_imports():
    mod = parse_python("import os\nfrom a.b import c\nfrom . import d\n")
    levels = {(i.level, i.module) for i in mod.imports}
    assert (0, "os") in levels
    assert (0, "a.b") in levels
    assert (1, None) in levels


def test_python_syntax_error_is_safe():
    assert parse_python("def (:\n").symbols == []


def test_references_three_kinds():
    text = "Link [x](a/b.py). Wiki [[Note]]. Prose mentions src/util.py here. http://skip.me/x.py"
    refs = extract_references(text)
    kinds = {t: k for t, k in refs}
    assert kinds.get("a/b.py") == "link"
    assert kinds.get("Note") == "wikilink"
    assert kinds.get("src/util.py") == "path"
    assert all("skip.me" not in t for t, _ in refs)


def test_references_dedupe_first_seen():
    refs = extract_references("a.py and again a.py")
    assert [t for t, _ in refs].count("a.py") == 1


def test_decisions():
    ids = extract_decisions("See ADR-7 and RFC-12 and D-FOO-3 and ADR-7 again.")
    assert ids == ["ADR-7", "RFC-12", "D-FOO-3"]
