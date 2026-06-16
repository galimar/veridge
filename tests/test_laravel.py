from __future__ import annotations

import pytest

from veridge import laravel
from veridge.model import EdgeType, Kind


# -- pure heuristics (no tree-sitter needed) --------------------------------
def test_is_route_file():
    assert laravel.is_route_file("routes/web.php")
    assert laravel.is_route_file("routes/api.php")
    assert laravel.is_route_file("app/routes/admin.php")
    assert not laravel.is_route_file("app/Http/Controllers/UserController.php")
    assert not laravel.is_route_file("routes/web.js")


def test_is_event_provider():
    assert laravel.is_event_provider("app/Providers/EventServiceProvider.php")
    assert not laravel.is_event_provider("app/Providers/RouteServiceProvider.php")


def test_route_class_refs():
    src = ("<?php\nuse App\\Http\\Controllers\\UserController;\n"
           "Route::get('/u', [UserController::class, 'index']);\n"
           "Route::post('/u', [UserController::class, 'store']);\n")
    assert laravel.route_class_refs(src) == ["UserController"]


def test_event_listener_pairs():
    src = ("<?php\nclass EventServiceProvider {\n"
           "  protected $listen = [\n"
           "    UserRegistered::class => [\n"
           "      SendWelcomeEmail::class,\n"
           "      LogRegistration::class,\n"
           "    ],\n"
           "  ];\n}\n")
    pairs = laravel.event_listener_pairs(src)
    assert pairs == [("UserRegistered", ["SendWelcomeEmail", "LogRegistration"])]


# -- end-to-end wiring through the indexer (needs PHP symbols) --------------
pytest.importorskip("tree_sitter_language_pack")
from veridge.freshness import index  # noqa: E402


def _build(tmp_path):
    (tmp_path / "app" / "Http" / "Controllers").mkdir(parents=True)
    (tmp_path / "app" / "Listeners").mkdir(parents=True)
    (tmp_path / "app" / "Events").mkdir(parents=True)
    (tmp_path / "app" / "Providers").mkdir(parents=True)
    (tmp_path / "routes").mkdir()

    (tmp_path / "app" / "Http" / "Controllers" / "UserController.php").write_text(
        "<?php\nclass UserController { public function index(){ return 1; } }\n",
        encoding="utf-8")
    (tmp_path / "app" / "Events" / "UserRegistered.php").write_text(
        "<?php\nclass UserRegistered {}\n", encoding="utf-8")
    (tmp_path / "app" / "Listeners" / "SendWelcomeEmail.php").write_text(
        "<?php\nclass SendWelcomeEmail { public function handle($e){} }\n", encoding="utf-8")
    (tmp_path / "routes" / "web.php").write_text(
        "<?php\nRoute::get('/u', [UserController::class, 'index']);\n", encoding="utf-8")
    (tmp_path / "app" / "Providers" / "EventServiceProvider.php").write_text(
        "<?php\nclass EventServiceProvider {\n"
        "  protected $listen = [ UserRegistered::class => [ SendWelcomeEmail::class ] ];\n}\n",
        encoding="utf-8")
    g, _ = index(tmp_path)
    return g


def test_route_wires_to_controller(tmp_path):
    g = _build(tmp_path)
    refs = {(e.source, e.target) for e in g.edges if e.type is EdgeType.REFERENCES}
    assert ("routes/web.php",
            "app/Http/Controllers/UserController.php#UserController") in refs


def test_listener_references_event_so_impact_finds_it(tmp_path):
    g = _build(tmp_path)
    refs = {(e.source, e.target) for e in g.edges if e.type is EdgeType.REFERENCES}
    # listener -> event, so the blast-radius of the event reaches its listener
    assert ("app/Listeners/SendWelcomeEmail.php#SendWelcomeEmail",
            "app/Events/UserRegistered.php#UserRegistered") in refs

    from veridge.impact import dependents
    event_id = "app/Events/UserRegistered.php#UserRegistered"
    affected = dependents(g, [event_id])
    assert "app/Listeners/SendWelcomeEmail.php#SendWelcomeEmail" in affected


def test_symbol_kinds_are_classes(tmp_path):
    g = _build(tmp_path)
    classes = {n.id for n in g.nodes.values()
               if n.kind is Kind.SYMBOL and n.meta.get("symbol") == "class"}
    assert "app/Http/Controllers/UserController.php#UserController" in classes
