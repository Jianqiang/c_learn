"""CLI/runtime configuration (plan section 13.2 suggested layout: `data/
learning.db`).

This is intentionally the smallest possible module: a single default path
plus a one-line override resolver. It exists as its own file (rather than a
constant inlined into cli.py) purely so tests and future callers (a future
Web layer per plan 12.2, which "必须调用相同的 service layer") can import the
same default without importing the whole Typer app.
"""
from __future__ import annotations

from pathlib import Path

# Plan 13.2's suggested tree puts the SQLite file at data/learning.db,
# relative to wherever the tool is invoked from (this is a local-first,
# single-user tool -- there is no server-side "project root" to resolve
# against, so cwd-relative is the deliberate choice here).
DEFAULT_DB_PATH = Path("data/learning.db")


def resolve_db_path(db: str | None) -> Path:
    """Return the effective database path for a CLI invocation: the
    explicit `--db` override if given, otherwise DEFAULT_DB_PATH."""
    return Path(db) if db else DEFAULT_DB_PATH
