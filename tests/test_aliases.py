from __future__ import annotations

from veridge.aliases import load_aliases
from veridge.freshness import index
from veridge.model import EdgeType


def test_load_aliases_from_tsconfig(tmp_path):
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions":{"baseUrl":".","paths":'
        '{"@/*":["src/*"],"@c/*":["src/components/*"]}}}', encoding="utf-8")
    (tmp_path / "src").mkdir()
    rules = dict(load_aliases(tmp_path))
    assert rules["@/"] == "src"
    assert rules["@c/"] == "src/components"


def test_load_aliases_jsonc_tolerant(tmp_path):
    # comments + trailing commas (JSONC) are tolerated
    (tmp_path / "jsconfig.json").write_text(
        '{\n  // paths\n  "compilerOptions": { "paths": { "~/*": ["app/*"], } },\n}\n',
        encoding="utf-8")
    assert dict(load_aliases(tmp_path))["~/"] == "app"


def test_default_src_aliases(tmp_path):
    (tmp_path / "src").mkdir()
    rules = dict(load_aliases(tmp_path))
    assert rules.get("@/") == "src" and rules.get("~/") == "src"


def test_no_aliases_without_config_or_src(tmp_path):
    assert load_aliases(tmp_path) == []


def test_indexer_resolves_vue_and_alias_import(tmp_path):
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', encoding="utf-8")
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "components" / "Button.vue").write_text(
        "<script>export function press(){}</script>", encoding="utf-8")
    (tmp_path / "src" / "App.vue").write_text(
        '<script>import { press } from "@/components/Button"</script>', encoding="utf-8")
    g, _ = index(tmp_path)
    imports = {(e.source, e.target) for e in g.edges if e.type is EdgeType.IMPORTS}
    # the aliased import resolved across the alias + the .vue suffix
    assert ("src/App.vue", "src/components/Button.vue") in imports
