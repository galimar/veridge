"""Enable ``python -m veridge`` as an alias for the ``veridge`` CLI."""

from __future__ import annotations

from veridge.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
