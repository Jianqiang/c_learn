"""Backup & export service (plan 7.1 'SQLite 单文件 backup，支持从 backup 恢复';
plan 12.1 `learn export --out <path>`; plan 14 M0 acceptance 'SQLite 单文件
backup 和 JSON export 的最小命令可用').

Two independent, deliberately separate capabilities:

backup_database() / restore_database()
    A full-fidelity, restorable copy of the whole database file, produced
    with sqlite3.Connection.backup() (the online backup API) rather than a
    raw file copy. backup() is safe to call against a live connection with
    a session in flight -- it uses SQLite's own page-level locking, so it
    can't capture a half-written page the way `cp` or `shutil.copy` could
    if a write landed mid-copy. This is the only path plan 7.1 requires to
    round-trip ("支持从 backup 恢复"): restore_database() copies a backup
    file back onto a target path, so the *backup format* is just another
    SQLite file, not a bespoke serialization.

    restore_database() refuses to treat an arbitrary file as a backup: if
    the source can't even be opened as SQLite, or opens but is missing the
    schema_migrations table this project's own init_db() always creates, it
    raises ValueError rather than silently producing a target DB that looks
    fine until the first repository call 500s on "no such table". This is
    a deliberate guard against restoring the wrong file by path typo.

export_json() / export_csv()
    Human-/tool-readable dumps of the key runtime tables (EXPORT_TABLES),
    one file per table. These are exports, not backups: nothing in v1
    reads a JSON/CSV export back into SQLite. Plan 7.1 only requires
    backup/restore to round-trip through SQLite's own format; export exists
    for external review, migration, or spreadsheet analysis, and quietly
    changing that contract later (e.g. adding an import_json()) should not
    be assumed compatible with what these functions produce today.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

EXPORT_TABLES: tuple[str, ...] = (
    "modules",
    "sources",
    "concepts",
    "concept_sources",
    "items",
    "sessions",
    "attempts",
    "review_state",
    "applications",
    "learning_outputs",
    "status_events",
    "focus_state",
)

_REQUIRED_TABLE_FOR_VALIDATION = "schema_migrations"


def backup_database(conn: sqlite3.Connection, backup_dir: str | Path, *, now: datetime) -> Path:
    """Write a full online-backup copy of `conn`'s database to
    `backup_dir/learning_<YYYYMMDD_HHMMSS>.db` and return that path.

    Safe to call against a connection with an open transaction/session in
    progress: sqlite3's backup() API copies page-by-page under SQLite's own
    locking, unlike a raw file copy which could catch a write mid-flight.
    """
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = f"learning_{now.strftime('%Y%m%d_%H%M%S')}.db"
    target_path = backup_dir / filename

    target_conn = sqlite3.connect(str(target_path))
    try:
        conn.backup(target_conn)
    finally:
        target_conn.close()
    return target_path


def restore_database(backup_path: str | Path, target_path: str | Path) -> Path:
    """Copy `backup_path` (a file previously produced by backup_database(),
    or any SQLite file with this project's schema) onto `target_path`,
    overwriting whatever is currently at `target_path`.

    Raises FileNotFoundError if `backup_path` does not exist, and
    ValueError if it exists but is not a valid SQLite database for this
    project (not SQLite at all, or missing schema_migrations) -- restoring
    such a file would silently produce a target DB that fails on the first
    real query instead of failing loudly here, at the point where the
    caller can still notice they gave the wrong path.
    """
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(f"backup file not found: {backup_path}")

    source_conn = sqlite3.connect(str(backup_path))
    try:
        try:
            tables = {
                row[0]
                for row in source_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"{backup_path} is not a valid SQLite database: {exc}") from exc
        if _REQUIRED_TABLE_FOR_VALIDATION not in tables:
            raise ValueError(
                f"{backup_path} does not look like a learning_os database "
                f"(missing '{_REQUIRED_TABLE_FOR_VALIDATION}' table)"
            )

        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()

        target_conn = sqlite3.connect(str(target_path))
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()
    return target_path


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def export_json(
    conn: sqlite3.Connection,
    out_dir: str | Path,
    tables: Iterable[str] = EXPORT_TABLES,
) -> dict[str, Path]:
    """Write `<out_dir>/<table>.json` for each table in `tables`, each file
    a JSON array of objects (one per row, keyed by column name). An empty
    table still produces a valid `[]`, never an error or a missing file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for table in tables:
        columns = _table_columns(conn, table)
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        records = [dict(zip(columns, row)) for row in rows]
        path = out_dir / f"{table}.json"
        path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        result[table] = path
    return result


def export_csv(
    conn: sqlite3.Connection,
    out_dir: str | Path,
    tables: Iterable[str] = EXPORT_TABLES,
) -> dict[str, Path]:
    """Write `<out_dir>/<table>.csv` for each table in `tables`. Every file
    always has a header row (the table's column names) even when the table
    is empty, so downstream tooling can rely on the header being present.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for table in tables:
        columns = _table_columns(conn, table)
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        path = out_dir / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        result[table] = path
    return result
