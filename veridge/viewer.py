"""Render a self-contained, offline 3D-ish graph viewer as a single HTML file.

The graph data is inlined into the page and the renderer is hand-written vanilla JS on a
``<canvas>`` — **no CDN, no bundled library, no server**. Double-click the written
``.veridge/view.html`` and it works offline. Inlining is XSS-safe: the payload lives in a
non-executable ``<script type="application/json">`` block with every ``<`` escaped, so no
``</script>`` (or ``<!--``) in a file name or label can break out of it; ``JSON.parse`` decodes
it back.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from veridge.model import KIND_COLORS, Graph
from veridge.store import store_dir

_TEMPLATE = Path(__file__).parent / "ui" / "template.html"
_TOKEN = "__VERIDGE_DATA__"


def _payload(graph: Graph) -> dict:
    deg = {nid: graph.degree(nid) for nid in graph.nodes}
    nodes = [{
        "id": n.id, "kind": n.kind.value, "label": n.label,
        "path": n.path, "deg": deg.get(n.id, 0),
    } for n in graph.nodes.values()]
    links = [{"source": e.source, "target": e.target, "type": e.type.value}
             for e in graph.edges]
    return {
        "project": graph.project,
        "nodes": nodes,
        "links": links,
        "nodeColors": {k.value: v for k, v in KIND_COLORS.items()},
    }


def render_view(graph: Graph) -> str:
    """Return a standalone HTML document for ``graph``."""
    data = json.dumps(_payload(graph), ensure_ascii=False).replace("<", "\\u003c")
    try:
        template = _TEMPLATE.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"viewer template not found at {_TEMPLATE} — the package may be installed without "
            "its UI data files; reinstall veridge"
        ) from exc
    return template.replace(_TOKEN, data)


def write_view(root: str | os.PathLike[str], graph: Graph) -> Path:
    """Write the viewer to ``<root>/.veridge/view.html`` and return the path."""
    d = store_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    out = d / "view.html"
    out.write_text(render_view(graph), encoding="utf-8", newline="\n")
    return out
