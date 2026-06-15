from __future__ import annotations

from veridge import cli, query, viewer
from veridge.model import Edge, EdgeType, Graph, Kind, Node


def test_render_inlines_data_and_escapes_lt():
    g = Graph("demo")
    g.add_node(Node("a</script><x>.md", Kind.FILE, "a</script>", path="a"))
    g.add_node(Node("b.md", Kind.FILE, "b", path="b"))
    g.add_edge(Edge("a</script><x>.md", "b.md", EdgeType.REFERENCES))
    html = viewer.render_view(g)
    assert "__VERIDGE_DATA__" not in html          # token was substituted
    start = html.index('id="data"')
    block = html[start:html.index("</script>", start)]
    assert "<" not in block                         # every '<' in the payload is escaped
    assert "\\u003c" in block                        # ...to < (XSS-safe)


def test_write_view_creates_offline_html(graph, project):
    out = viewer.write_view(project, graph)
    assert out.is_file() and out.name == "view.html"
    text = out.read_text(encoding="utf-8")
    assert "Veridge" in text                          # template title
    assert "cdn" not in text.lower()                  # no external CDN
    assert "<canvas" in text                          # the vanilla-JS canvas renderer


def test_induced_subgraph(graph):
    sub = query.induced_subgraph(graph, {"src/app.py", "src/util.py", "nope"})
    assert set(sub.nodes) == {"src/app.py", "src/util.py"}
    assert any(e.source == "src/app.py" and e.target == "src/util.py" for e in sub.edges)


def test_backbone_keeps_areas(graph):
    bb = query.backbone(graph, limit=3)
    areas = {n.id for n in bb.nodes.values() if n.kind is Kind.AREA}
    assert areas                                      # area nodes are always kept
    assert len(bb.nodes) <= 3 + len(areas)


def test_view_cli(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["view", str(project)]) == 0
    assert "view written" in capsys.readouterr().out
    assert (project / ".veridge" / "view.html").is_file()


def test_view_focus_cli(project, capsys):
    cli.main(["build", str(project)])
    assert cli.main(["view", str(project), "--focus", "util"]) == 0
    assert "focus 'util'" in capsys.readouterr().out
