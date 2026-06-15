from __future__ import annotations

from veridge.layers import LAYER_ORDER, layer_of, layer_summary
from veridge.model import Category, Kind, Node


def test_layer_of_by_category_and_name(graph):
    assert layer_of(graph.nodes["src/app.py"]) == "entrypoint"
    assert layer_of(graph.nodes["src/util.py"]) == "util"
    assert layer_of(graph.nodes["README.md"]) == "docs"
    assert layer_of(graph.nodes["config.toml"]) == "config"
    assert layer_of(graph.nodes["data/big.csv"]) == "data"


def test_layer_of_tests_detection():
    n = Node("tests/test_foo.py", Kind.FILE, "test_foo.py", path="tests/test_foo.py",
             category=Category.CODE)
    assert layer_of(n) == "tests"


def test_layer_of_non_file_is_other(graph):
    area = next(n for n in graph.nodes.values() if n.kind is Kind.AREA)
    assert layer_of(area) == "other"


def test_layer_summary_is_ordered(graph):
    rows = layer_summary(graph)
    layers = [r["layer"] for r in rows]
    assert "entrypoint" in layers and "docs" in layers
    rank = {lay: i for i, lay in enumerate(LAYER_ORDER)}
    assert layers == sorted(layers, key=lambda x: rank[x])
    assert sum(r["files"] for r in rows) == 7  # every file lands in exactly one layer
