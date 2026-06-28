"""Command line: build, map, find, neighbors, focus, gate, stats.

Read-only on your sources: commands only read the project and write derived files under
``.veridge/``.
"""

from __future__ import annotations

import argparse
import json
import sys

from veridge import __version__, doctor, query, store
from veridge.freshness import build_manifest, evaluate, index
from veridge.model import Graph
from veridge.viewer import write_view


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.0f} {unit}" if unit == "B" else f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


def _load_or_build(path: str) -> Graph:
    return store.load_graph(path) or index(path)[0]


def cmd_build(args: argparse.Namespace) -> int:
    g, m = index(args.path)
    store.save(args.path, g, m)
    c = g.counts()
    print(f"built '{g.project}': {len(g.nodes)} nodes, {len(g.edges)} edges")
    print("  nodes:", c["nodes"])
    print("  edges:", c["edges"])
    print(f"  store: {store.store_dir(args.path)}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    g = _load_or_build(args.path)
    c = g.counts()
    print(f"'{g.project}': {len(g.nodes)} nodes, {len(g.edges)} edges")
    for k, v in sorted(c["nodes"].items()):
        print(f"  {k:9} {v}")
    for k, v in sorted(c["edges"].items()):
        print(f"  -{k:8} {v}")
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    m = query.project_map(_load_or_build(args.path))
    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=2))
        return 0
    print(f"{m['project']}: {m['files']} files · {m['symbols']} symbols · "
          f"{m['areas']} areas · {m['edges']} edges · {_human(m['size'])}")
    print("by area:")
    for a in m["by_area"]:
        print(f"  {a['area']:16} {a['files']:4} files  {_human(a['size']):>9}  "
              f"[{', '.join(a['top_cats'])}]")
    print("by layer:")
    for ly in m["by_layer"]:
        print(f"  {ly['layer']:11} {ly['files']:4} files  {_human(ly['size']):>9}")
    print("most important (PageRank):")
    for x in m["most_important"]:
        print(f"  {x['score']:.4f}  {x['id']}  ({x['kind']})")
    print(f"orphans: {m['orphans']} · broken refs: {m['broken_refs']}")
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    res = query.find(_load_or_build(args.path), args.query)
    for r in res:
        print(f"  {r['kind']:8} {r['id']}")
    print(f"({len(res)} matches)")
    return 0


def cmd_neighbors(args: argparse.Namespace) -> int:
    n = query.neighbors(_load_or_build(args.path), args.node)
    if n is None:
        print(f"node not found: {args.node}", file=sys.stderr)
        return 1
    print(f"{n['id']} ({n['kind']}) · {_human(n['size'])}")
    if n["description"]:
        print(f"  {n['description']}")
    if n["broken_refs"]:
        print(f"  broken refs: {n['broken_refs']}")
    print(f"  outgoing ({len(n['outgoing'])}):")
    for o in n["outgoing"]:
        print(f"    -{o['edge']}-> {o['id']} ({o['kind']})")
    print(f"  incoming ({len(n['incoming'])}):")
    for o in n["incoming"]:
        print(f"    <-{o['edge']}- {o['id']} ({o['kind']})")
    return 0


def cmd_focus(args: argparse.Namespace) -> int:
    res = query.focus(_load_or_build(args.path), args.query, budget_tokens=args.budget)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if not res["nodes"]:
        print(res.get("note", "no matches"))
        return 0
    print(f"focus '{res['query']}' · {len(res['nodes'])} nodes · "
          f"~{res['used_tokens']}/{res['budget_tokens']} tokens")
    print(f"  seeds: {', '.join(res['seeds'])}")
    for r in res["nodes"]:
        extra = f" ({r['cat']})" if r.get("cat") else ""
        print(f"  {r.get('score', 0):.4f}  {r['id']}{extra}  [{r['kind']}, deg {r['deg']}]")
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    seed_ids = None
    query_str = args.seed or ""
    proj = args.path
    if args.diff:
        # In --diff mode there is no seed, so a lone positional is the project path.
        if args.seed and args.path == ".":
            proj = args.seed
        from veridge.sessions import git_changed_files
        seed_ids = git_changed_files(proj)
        query_str = "git diff (HEAD)"
        if not seed_ids:
            print("no changed files vs HEAD (or not a git repository)")
            return 0
    elif not args.seed:
        print("provide a seed (file/symbol) or use --diff", file=sys.stderr)
        return 2
    g = _load_or_build(proj)
    direction = "dependencies" if args.deps else "dependents"
    res = query.impact(g, query_str, seed_ids=seed_ids, budget_tokens=args.budget,
                       hops=args.hops, direction=direction)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    verb = "depends on" if args.deps else "affected by"
    print(f"impact ({direction}) of '{res['query']}' · {res['total_affected']} {verb}")
    if res["seeds"]:
        print(f"  seeds: {', '.join(res['seeds'])}")
    if not res["nodes"]:
        print(f"  {res.get('note', 'nothing found')}")
        return 0
    print(f"  showing {len(res['nodes'])} · ~{res['used_tokens']}/{res['budget_tokens']} tokens")
    for r in res["nodes"]:
        extra = f" ({r['cat']})" if r.get("cat") else ""
        print(f"  {r.get('score', 0):.4f}  d{r.get('dist', '?')}  {r['id']}{extra}  [{r['kind']}]")
    return 0


def cmd_why(args: argparse.Namespace) -> int:
    res = query.why(_load_or_build(args.path), args.a, args.b)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if not res["found"]:
        print(res.get("note", "no path"))
        return 1
    path = res["path"]
    print(f"why: {res['a']} -> {res['b']} · {res['length']} hops")
    print(f"  {path[0]['id']} ({path[0]['kind']})")
    for step in path[1:]:
        connector = f"--{step['edge']}-->" if step["dir"] == "->" else f"<--{step['edge']}--"
        print(f"    {connector} {step['id']} ({step['kind']})")
    return 0


def cmd_tour(args: argparse.Namespace) -> int:
    res = query.tour(_load_or_build(args.path), budget_tokens=args.budget)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    print(f"tour of '{res['project']}' · {len(res['stops'])}/{res['total_files']} stops · "
          f"~{res['used_tokens']}/{res['budget_tokens']} tokens")
    print("(read top to bottom: dependencies before the files that use them)")
    for s in res["stops"]:
        print(f"  {s['step']:2}. {s['id']}  [{s['layer']}]")
        if s["uses"]:
            print(f"        uses: {', '.join(s['uses'])}")
        if s["used_by"]:
            print(f"        used by: {', '.join(s['used_by'])}")
    return 0


def cmd_integrate(args: argparse.Namespace) -> int:
    from veridge import integrate as integrator
    paths = integrator.integrate(args.path, args.assistant)
    print(f"integrated veridge for {args.assistant}:")
    for p in paths:
        print(f"  {p}")
    print("  (the MCP server needs the extra: pip install \"veridge[mcp]\")")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from veridge import export as exporter
    text = exporter.export(_load_or_build(args.path), args.format)
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.format} export: {args.out}")
    else:
        print(text)
    return 0


_BACKBONE_AUTO = 1500  # graphs bigger than this auto-render as a PageRank backbone


def cmd_view(args: argparse.Namespace) -> int:
    g = _load_or_build(args.path)
    full = len(g.nodes)
    if args.focus:
        res = query.focus(g, args.focus, budget_tokens=args.budget)
        ids = {r["id"] for r in res["nodes"]} | set(res["seeds"])
        g = query.induced_subgraph(g, ids)
        mode = f"focus '{args.focus}'"
    elif args.backbone or full > _BACKBONE_AUTO:
        g = query.backbone(g)
        mode = "backbone"
    else:
        mode = "full"
    out = write_view(args.path, g)
    print(f"view written: {out}")
    print(f"  {len(g.nodes)} of {full} nodes ({mode}) — open it in a browser (double-click).")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from pathlib import Path

    from veridge import watch as watcher
    print(f"watching {Path(args.path).resolve()} every {args.interval}s — Ctrl+C to stop")

    def on_change(diff: dict) -> None:
        print(f"  rebuilt: +{len(diff['added'])} / -{len(diff['removed'])} "
              f"/ ~{len(diff['changed'])}")

    try:
        watcher.watch(args.path, interval=args.interval, on_change=on_change)
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def cmd_install_hook(args: argparse.Namespace) -> int:
    from veridge import watch as watcher
    try:
        hook = watcher.install_post_commit_hook(args.path)
    except (FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"installed git post-commit hook: {hook}")
    print("  it runs 'veridge build' after each commit")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    g = store.load_graph(args.path)
    old = store.load_manifest(args.path)
    if g is None or old is None:
        print("no graph found — run 'veridge build' first", file=sys.stderr)
        return 2
    rep = evaluate(g, old, build_manifest(args.path))
    if getattr(args, "json", False):
        print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(rep.summary(detail=not getattr(args, "summary", False)))
        print("OK: fresh and clean" if rep.ok else "DRIFT: rebuild and/or fix the issues above")
    return 0 if rep.ok else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = doctor.diagnose(args.path)
    if getattr(args, "json", False):
        print(json.dumps(
            [{"name": c.name, "ok": c.ok, "detail": c.detail, "blocking": c.blocking}
             for c in checks], indent=2, ensure_ascii=False))
    else:
        for c in checks:
            mark = "ok" if c.ok else ("XX" if c.blocking else "--")
            print(f"  [{mark}] {c.name}: {c.detail}")
        blocking = [c for c in checks if c.blocking and not c.ok]
        gaps = [c for c in checks if not c.ok and not c.blocking]
        if blocking:
            print(f"not usable yet — {blocking[0].detail}")
        elif gaps:
            print(f"usable; {len(gaps)} optional setup step(s) above")
        else:
            print("all set")
    return 1 if any(c.blocking and not c.ok for c in checks) else 0


def main(argv: list[str] | None = None) -> int:
    # Print UTF-8 regardless of the console's locale (Windows defaults to cp1252, which
    # would mangle the '·' separators). Best-effort: ignore if the stream can't reconfigure.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        prog="veridge", description="Veridge — the always-fresh, low-token map of a project.",
        epilog="Files: in a git repo, indexing honours .gitignore (via git). Add a .veridgeignore "
               "(one glob per line) for extra excludes. Run 'veridge <command> -h' for a command's "
               "options.")
    parser.add_argument("--version", action="version", version=f"veridge {__version__}")
    sub = parser.add_subparsers(dest="cmd", metavar="<command>")

    for name, fn, help_text in [
        ("build", cmd_build, "index the project -> .veridge/graph.json"),
        ("stats", cmd_stats, "counts by node/edge type"),
    ]:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
        sp.set_defaults(func=fn)

    sp = sub.add_parser("gate", help="anti-drift check (broken refs, stale files, orphans)")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--summary", action="store_true",
                    help="counts + verdict only, no per-reference detail (handy for large repos)")
    sp.add_argument("--json", action="store_true", help="emit JSON (for CI)")
    sp.set_defaults(func=cmd_gate)

    sp = sub.add_parser("doctor", help="check Veridge setup here (index, extras, MCP wiring)")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--json", action="store_true", help="emit JSON")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("map", help="compact project digest (PageRank-ranked)")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--json", action="store_true", help="emit JSON")
    sp.set_defaults(func=cmd_map)

    sp = sub.add_parser("find", help="find nodes by name/path substring")
    sp.add_argument("query", help="substring to search for")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.set_defaults(func=cmd_find)

    sp = sub.add_parser("neighbors", help="a node and its connections")
    sp.add_argument("node", help="node id")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.set_defaults(func=cmd_neighbors)

    sp = sub.add_parser("focus", help="minimal relevant subgraph for a task, within a budget")
    sp.add_argument("query", help="a task description, a file path, or a symbol name")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--budget", type=int, default=1500, help="token budget (default: 1500)")
    sp.add_argument("--json", action="store_true", help="emit JSON")
    sp.set_defaults(func=cmd_focus)

    sp = sub.add_parser("impact", help="blast-radius: what a change to a file/symbol affects")
    sp.add_argument("seed", nargs="?", help="a file path or symbol name (omit with --diff)")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--diff", action="store_true", help="seed from files changed vs git HEAD")
    sp.add_argument("--deps", action="store_true",
                    help="invert: what the seed depends ON, not what depends on it")
    sp.add_argument("--hops", type=int, default=None, help="max propagation distance")
    sp.add_argument("--budget", type=int, default=1500, help="token budget (default: 1500)")
    sp.add_argument("--json", action="store_true", help="emit JSON")
    sp.set_defaults(func=cmd_impact)

    sp = sub.add_parser("why", help="shortest typed path between two nodes")
    sp.add_argument("a", help="first node (id, path, or name)")
    sp.add_argument("b", help="second node (id, path, or name)")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--json", action="store_true", help="emit JSON")
    sp.set_defaults(func=cmd_why)

    sp = sub.add_parser("tour", help="dependency-ordered reading tour of the key files")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--budget", type=int, default=2000, help="token budget (default: 2000)")
    sp.add_argument("--json", action="store_true", help="emit JSON")
    sp.set_defaults(func=cmd_tour)

    sp = sub.add_parser("view", help="write a self-contained offline graph viewer (HTML)")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--focus", metavar="QUERY",
                    help="render only the focus subgraph for a task/file/symbol")
    sp.add_argument("--backbone", action="store_true",
                    help="render only the PageRank core (auto for large graphs)")
    sp.add_argument("--budget", type=int, default=1500,
                    help="token budget for --focus (default: 1500)")
    sp.set_defaults(func=cmd_view)

    sp = sub.add_parser("watch", help="rebuild automatically when files change (poll loop)")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--interval", type=float, default=2.0, help="poll seconds (default: 2.0)")
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser("install-hook", help="add a git post-commit hook that runs 'veridge build'")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.set_defaults(func=cmd_install_hook)

    sp = sub.add_parser("export", help="export the graph to an interchange format")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--format", choices=["native", "jgf", "dot"], default="jgf",
                    help="output format (default: jgf)")
    sp.add_argument("--out", metavar="FILE", help="write to FILE instead of stdout")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("integrate",
                        help="wire veridge into an assistant (MCP server + steering note)")
    sp.add_argument("assistant", choices=["claude", "codex"], help="which assistant to set up")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.set_defaults(func=cmd_integrate)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):        # no command given -> show the full help, not a terse error
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
