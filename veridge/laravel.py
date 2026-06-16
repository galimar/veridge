"""Heuristics for Laravel's convention-based wiring that static call-graphing misses.

Laravel connects pieces by **class-name strings and convention**, not direct calls: a route
file maps URLs to controllers (``[UserController::class, 'index']``), and the
``EventServiceProvider`` maps events to listeners (``Registered::class => [SendEmail::class]``).
This module recognises those two patterns so the graph reflects the wiring — a route file links
to its controllers, an event links to its listeners — and ``impact``/``focus`` can follow it.

Best-effort and regex-based: it only emits a link for a class name it can resolve to a class
*already in the graph*, so it needs the ``[treesitter]`` extra (which provides PHP symbols).
"""

from __future__ import annotations

import re

_CLASS_REF = re.compile(r"\b([A-Za-z_]\w*)::class\b")
# An ``Event::class => [Listener::class, ...]`` entry of the EventServiceProvider's $listen array.
_LISTEN_ENTRY = re.compile(r"\b([A-Za-z_]\w*)::class\s*=>\s*\[([^\]]*)\]", re.DOTALL)


def is_route_file(rel: str) -> bool:
    """A PHP file under a ``routes/`` directory (web.php, api.php, …)."""
    parts = rel.split("/")
    return rel.endswith(".php") and "routes" in parts[:-1]


def is_event_provider(rel: str) -> bool:
    return rel.rsplit("/", 1)[-1] == "EventServiceProvider.php"


def is_wiring_file(rel: str) -> bool:
    return is_route_file(rel) or is_event_provider(rel)


def route_class_refs(text: str) -> list[str]:
    """Class names referenced as ``X::class`` in a route file (controllers, middleware, …)."""
    return list(dict.fromkeys(m.group(1) for m in _CLASS_REF.finditer(text)))


def event_listener_pairs(text: str) -> list[tuple[str, list[str]]]:
    """``(event_class, [listener_classes])`` pairs from a ``$listen`` array."""
    out: list[tuple[str, list[str]]] = []
    for m in _LISTEN_ENTRY.finditer(text):
        listeners = list(dict.fromkeys(x.group(1) for x in _CLASS_REF.finditer(m.group(2))))
        if listeners:
            out.append((m.group(1), listeners))
    return out
