"""TDD for backup & export commands (plan 7.1: 'SQLite 单文件 backup，支持从
backup 恢复', plan 12.1: `learn export --out <path>`, plan 14 M0 acceptance:
'SQLite 单文件 backup 和 JSON export 的最小命令可用').

Two independent capabilities under test:

1. backup_database() / restore_database(): a full-fidelity, restorable
   single-file SQLite copy using sqlite3's own online backup API (safe to
   call against a live, open connection -- unlike a raw file copy, which
   could catch the DB mid-write) rather than exporting/re-importing rows.
2. export_json() / export_csv(): human-/tool-readable dumps of the key
   runtime tables, one file per table, for review or migration outside
   SQLite. These are exports, not backups -- restoring from them is out of
   scope for v1 (plan 7.1 only requires backup/restore to round-trip
   through SQLite's own format).
"""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime

import pytest

from learning_os.db import init_db
from learning_os.repositories import ConceptRepository, ModuleRepository
from learning_os.services.backup_service import (
    EXPORT_TABLES,
    backup_database,
    export_csv,
    export_json,
    restore_database,
)

NOW = datetime(2026, 1, 1, 12, 0, 0)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "learning.db"
    c = init_db(db_path)
    yield c
    c.close()


@pytest.fixture()
def seeded_conn(conn):
    module = ModuleRepository(conn).create(slug="m1", name="Module 1", phase=1)
    ConceptRepository(conn).create(module_id=module.id, slug="c1", name="Concept 1")
    return conn


# ---------------------------------------------------------------------------
# backup_database() / restore_database()
# ---------------------------------------------------------------------------

def test_backup_creates_a_file_in_the_backup_dir(seeded_conn, tmp_path):
    backup_dir = tmp_path / "backups"
    path = backup_database(seeded_conn, backup_dir, now=NOW)
    assert path.exists()
    assert path.parent == backup_dir


def test_backup_creates_backup_dir_if_missing(seeded_conn, tmp_path):
    backup_dir = tmp_path / "does" / "not" / "exist"
    path = backup_database(seeded_conn, backup_dir, now=NOW)
    assert path.exists()


def test_backup_filename_includes_timestamp(seeded_conn, tmp_path):
    path = backup_database(seeded_conn, tmp_path / "backups", now=NOW)
    assert "20260101" in path.name
    assert path.suffix == ".db"


def test_backup_two_calls_at_different_times_produce_distinct_files(seeded_conn, tmp_path):
    backup_dir = tmp_path / "backups"
    p1 = backup_database(seeded_conn, backup_dir, now=NOW)
    p2 = backup_database(seeded_conn, backup_dir, now=datetime(2026, 1, 2, 9, 0, 0))
    assert p1 != p2
    assert p1.exists() and p2.exists()


def test_backup_is_a_valid_standalone_sqlite_db_with_same_data(seeded_conn, tmp_path):
    path = backup_database(seeded_conn, tmp_path / "backups", now=NOW)
    check_conn = sqlite3.connect(str(path))
    try:
        row = check_conn.execute("SELECT slug, name, phase FROM modules WHERE slug='m1'").fetchone()
        assert row == ("m1", "Module 1", 1)
        row2 = check_conn.execute("SELECT slug, name FROM concepts WHERE slug='c1'").fetchone()
        assert row2 == ("c1", "Concept 1")
    finally:
        check_conn.close()


def test_restore_recovers_data_into_a_fresh_target(seeded_conn, tmp_path):
    backup_path = backup_database(seeded_conn, tmp_path / "backups", now=NOW)

    target_path = tmp_path / "restored" / "learning.db"
    restore_database(backup_path, target_path)

    restored_conn = sqlite3.connect(str(target_path))
    try:
        row = restored_conn.execute("SELECT slug, name FROM modules WHERE slug='m1'").fetchone()
        assert row == ("m1", "Module 1")
    finally:
        restored_conn.close()


def test_restore_overwrites_an_existing_target_file(conn, seeded_conn, tmp_path):
    backup_path = backup_database(seeded_conn, tmp_path / "backups", now=NOW)

    # target already has *different* data before restore
    target_path = tmp_path / "learning.db"
    stale_conn = init_db(target_path)
    ModuleRepository(stale_conn).create(slug="stale", name="Stale Module", phase=1)
    stale_conn.close()

    restore_database(backup_path, target_path)

    restored_conn = sqlite3.connect(str(target_path))
    try:
        assert restored_conn.execute(
            "SELECT 1 FROM modules WHERE slug='stale'"
        ).fetchone() is None
        assert restored_conn.execute(
            "SELECT 1 FROM modules WHERE slug='m1'"
        ).fetchone() is not None
    finally:
        restored_conn.close()


def test_restore_raises_for_missing_backup_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        restore_database(tmp_path / "nope.db", tmp_path / "target.db")


def test_restore_rejects_a_non_learning_os_sqlite_file(tmp_path):
    bogus = tmp_path / "bogus.db"
    bogus_conn = sqlite3.connect(str(bogus))
    bogus_conn.execute("CREATE TABLE unrelated (id INTEGER)")
    bogus_conn.commit()
    bogus_conn.close()

    with pytest.raises(ValueError):
        restore_database(bogus, tmp_path / "target.db")


def test_restore_rejects_a_non_sqlite_file(tmp_path):
    not_a_db = tmp_path / "not_a_db.db"
    not_a_db.write_text("hello, this is not sqlite")

    with pytest.raises(ValueError):
        restore_database(not_a_db, tmp_path / "target.db")


def test_restore_creates_target_parent_dir_if_missing(seeded_conn, tmp_path):
    backup_path = backup_database(seeded_conn, tmp_path / "backups", now=NOW)
    target_path = tmp_path / "nested" / "dir" / "learning.db"
    restore_database(backup_path, target_path)
    assert target_path.exists()


# ---------------------------------------------------------------------------
# export_json()
# ---------------------------------------------------------------------------

def test_export_json_writes_one_file_per_table(seeded_conn, tmp_path):
    out_dir = tmp_path / "export"
    paths = export_json(seeded_conn, out_dir)
    assert set(paths.keys()) == set(EXPORT_TABLES)
    for table, path in paths.items():
        assert path.exists()
        assert path.name == f"{table}.json"


def test_export_json_creates_out_dir_if_missing(seeded_conn, tmp_path):
    out_dir = tmp_path / "brand" / "new" / "export"
    export_json(seeded_conn, out_dir)
    assert out_dir.exists()


def test_export_json_produces_valid_parseable_json_for_every_table(seeded_conn, tmp_path):
    paths = export_json(seeded_conn, tmp_path / "export")
    for path in paths.values():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)


def test_export_json_modules_table_content_matches_row(seeded_conn, tmp_path):
    paths = export_json(seeded_conn, tmp_path / "export")
    modules = json.loads(paths["modules"].read_text(encoding="utf-8"))
    assert len(modules) == 1
    assert modules[0]["slug"] == "m1"
    assert modules[0]["name"] == "Module 1"
    assert modules[0]["phase"] == 1


def test_export_json_empty_table_produces_empty_array_not_error(seeded_conn, tmp_path):
    paths = export_json(seeded_conn, tmp_path / "export")
    sessions = json.loads(paths["sessions"].read_text(encoding="utf-8"))
    assert sessions == []


def test_export_json_can_be_restricted_to_a_subset_of_tables(seeded_conn, tmp_path):
    paths = export_json(seeded_conn, tmp_path / "export", tables=("modules", "concepts"))
    assert set(paths.keys()) == {"modules", "concepts"}


# ---------------------------------------------------------------------------
# export_csv()
# ---------------------------------------------------------------------------

def test_export_csv_writes_one_file_per_table(seeded_conn, tmp_path):
    out_dir = tmp_path / "export"
    paths = export_csv(seeded_conn, out_dir)
    assert set(paths.keys()) == set(EXPORT_TABLES)
    for table, path in paths.items():
        assert path.exists()
        assert path.name == f"{table}.csv"


def test_export_csv_creates_out_dir_if_missing(seeded_conn, tmp_path):
    out_dir = tmp_path / "brand" / "new" / "export"
    export_csv(seeded_conn, out_dir)
    assert out_dir.exists()


def test_export_csv_modules_has_header_and_data_row(seeded_conn, tmp_path):
    paths = export_csv(seeded_conn, tmp_path / "export")
    with paths["modules"].open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][:4] == ["id", "slug", "name", "phase"]
    data_row = rows[1]
    assert "m1" in data_row
    assert "Module 1" in data_row


def test_export_csv_empty_table_has_header_only(seeded_conn, tmp_path):
    paths = export_csv(seeded_conn, tmp_path / "export")
    with paths["sessions"].open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 1  # header row only, no data rows
