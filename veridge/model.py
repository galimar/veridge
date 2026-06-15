"""The graph model: typed nodes, typed edges, and an indexed container.

Two deliberate choices set this apart from a naive edge list:

* **Symbols are first-class nodes.** A file can contain ``symbol`` nodes (a function or a
  class) so the graph reasons at the granularity an assistant actually edits, not just
  whole files.
* **Adjacency is indexed.** The container keeps out/in/undirected adjacency maps, so
  ``neighbors``, ranking and budgeted traversal are O(degree), not O(edges) per call.

The whole structure serializes to plain JSON and rebuilds its indices on load.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Bumped when the on-disk graph.json shape changes in a backwards-incompatible way. Readers
# may use it to refuse or adapt; ``from_dict`` itself stays permissive (ignores unknown keys).
SCHEMA_VERSION = 1


class Kind(str, Enum):
    """What a node *is*. Drives colour and how queries treat it."""

    FILE = "file"          # a file on disk
    SYMBOL = "symbol"      # a function/class/method defined inside a file
    AREA = "area"          # a logical cluster (top-level directory)
    DECISION = "decision"  # a recorded decision (ADR / RFC / D-XXX)
    SESSION = "session"    # a work session (a git commit)


class Category(str, Enum):
    """Finer typing for FILE nodes (None for non-file kinds)."""

    STRUCTURE = "structure"  # README / foundation docs
    DOC = "doc"              # prose: reports, designs, notes
    CODE = "code"            # source files
    CONFIG = "config"        # configuration
    DATA = "data"            # datasets / databases
    MEMORY = "memory"        # persistent memory files


class EdgeType(str, Enum):
    """What a relationship *means*. Edges are directed source -> target."""

    DEFINES = "defines"        # file -> symbol it declares
    IMPORTS = "imports"        # code -> code (module/file level)
    CALLS = "calls"            # symbol -> symbol it invokes
    REFERENCES = "references"  # doc -> file (link / wikilink / path-in-prose)
    BELONGS_TO = "belongs_to"  # node -> area
    MENTIONS = "mentions"      # doc -> decision
    TOUCHES = "touches"        # session -> file changed in that commit


# How much each edge type counts when ranking relevance (undirected). Structural code
# relationships dominate; membership/touches are weak hints. Single source of truth.
EDGE_WEIGHT: dict[EdgeType, float] = {
    EdgeType.DEFINES: 1.0,
    EdgeType.IMPORTS: 1.0,
    EdgeType.CALLS: 1.0,
    EdgeType.REFERENCES: 0.8,
    EdgeType.MENTIONS: 0.6,
    EdgeType.TOUCHES: 0.3,
    EdgeType.BELONGS_TO: 0.15,
}

KIND_COLORS: dict[Kind, str] = {
    Kind.FILE: "#2563EB",
    Kind.SYMBOL: "#16A34A",
    Kind.AREA: "#6B7280",
    Kind.DECISION: "#DC2626",
    Kind.SESSION: "#92400E",
}


@dataclass
class Node:
    id: str
    kind: Kind
    label: str
    path: str | None = None
    category: Category | None = None
    description: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "path": self.path,
            "category": self.category.value if self.category else None,
            "description": self.description,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Node:
        cat = d.get("category")
        return cls(
            id=d["id"],
            kind=Kind(d["kind"]),
            label=d["label"],
            path=d.get("path"),
            category=Category(cat) if cat else None,
            description=d.get("description", ""),
            meta=dict(d.get("meta", {})),
        )


@dataclass
class Edge:
    source: str
    target: str
    type: EdgeType
    meta: dict[str, Any] = field(default_factory=dict)

    def key(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.type.value)

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target,
                "type": self.type.value, "meta": self.meta}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Edge:
        return cls(source=d["source"], target=d["target"],
                   type=EdgeType(d["type"]), meta=dict(d.get("meta", {})))


class Graph:
    """Indexed container of nodes and edges. Adjacency is kept in sync on every add."""

    def __init__(self, project: str = "") -> None:
        self.project = project
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._edge_keys: set[tuple[str, str, str]] = set()
        # Adjacency indices (id -> list of (other_id, edge_index)).
        self._out: dict[str, list[int]] = {}
        self._in: dict[str, list[int]] = {}
        # Cached symmetric weight map for ranking; rebuilt lazily, cleared on edge add.
        self._und_cache: dict[str, dict[str, float]] | None = None

    # -- mutation -----------------------------------------------------------
    def add_node(self, node: Node) -> Node:
        existing = self.nodes.get(node.id)
        if existing is not None:
            return existing
        self.nodes[node.id] = node
        return node

    def add_edge(self, edge: Edge) -> bool:
        k = edge.key()
        if k in self._edge_keys:
            return False
        self._edge_keys.add(k)
        idx = len(self.edges)
        self.edges.append(edge)
        self._out.setdefault(edge.source, []).append(idx)
        self._in.setdefault(edge.target, []).append(idx)
        self._und_cache = None  # adjacency changed -> invalidate the ranking cache
        return True

    # -- queries (O(degree), thanks to the adjacency index) -----------------
    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def out_edges(self, node_id: str) -> list[Edge]:
        return [self.edges[i] for i in self._out.get(node_id, [])]

    def in_edges(self, node_id: str) -> list[Edge]:
        return [self.edges[i] for i in self._in.get(node_id, [])]

    def degree(self, node_id: str) -> int:
        return len(self._out.get(node_id, [])) + len(self._in.get(node_id, []))

    def neighbors(self, node_id: str) -> set[str]:
        out = {self.edges[i].target for i in self._out.get(node_id, [])}
        inc = {self.edges[i].source for i in self._in.get(node_id, [])}
        return out | inc

    def is_orphan(self, node_id: str) -> bool:
        """True for a file node wired to nothing but its area (only ``belongs_to`` edges).

        The single definition of "orphan", shared by the digest and the gate so the two can
        never disagree.
        """
        n = self.nodes.get(node_id)
        if n is None or n.kind is not Kind.FILE:
            return False
        idxs = self._out.get(node_id, []) + self._in.get(node_id, [])
        return all(self.edges[i].type is EdgeType.BELONGS_TO for i in idxs)

    def undirected_weights(self) -> dict[str, dict[str, float]]:
        """Symmetric neighbour->weight map used by ranking (built once, then cached)."""
        if self._und_cache is not None:
            return self._und_cache
        adj: dict[str, dict[str, float]] = {}
        for e in self.edges:
            w = EDGE_WEIGHT.get(e.type, 0.5)
            adj.setdefault(e.source, {})
            adj.setdefault(e.target, {})
            adj[e.source][e.target] = adj[e.source].get(e.target, 0.0) + w
            adj[e.target][e.source] = adj[e.target].get(e.source, 0.0) + w
        self._und_cache = adj
        return adj

    def counts(self) -> dict[str, dict[str, int]]:
        nk: dict[str, int] = {}
        et: dict[str, int] = {}
        for n in self.nodes.values():
            nk[n.kind.value] = nk.get(n.kind.value, 0) + 1
        for e in self.edges:
            et[e.type.value] = et.get(e.type.value, 0) + 1
        return {"nodes": nk, "edges": et}

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        nodes = sorted(self.nodes.values(), key=lambda n: n.id)
        edges = sorted(self.edges, key=lambda e: (e.source, e.target, e.type.value))
        return {
            "schema_version": SCHEMA_VERSION,
            "project": self.project,
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Graph:
        g = cls(project=d.get("project", ""))
        for nd in d.get("nodes", []):
            g.add_node(Node.from_dict(nd))
        for ed in d.get("edges", []):
            g.add_edge(Edge.from_dict(ed))
        return g
