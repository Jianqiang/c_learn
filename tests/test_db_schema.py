"""Tests for schema creation and the migration runner.

TDD focus: given a fresh SQLite file, init_db() must create every table listed
in the tech plan (section 7.2), record the schema version, and be safe to call
repeatedly (idempotent) without dropping data or raising errors.
"""
import sqlite3

import pytest

from learning_os.db import CURRENT_SCHEMA_VERSION, get_schema_version, init_db

EXPECTED_TABLES = {
    "schema_migrations",
    "modules",
    "sources",
    "concepts",
    "focus_state",
    "learning_outputs",
    "concept_sources",
    "items",
    "sessions",
    "attempts",
    "review_state",
    "applications",
    "status_events",
}


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "learning.db"


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_init_db_creates_all_expected_tables(db_path):
    conn = init_db(db_path)
    try:
        assert EXPECTED_TABLES.issubset(_table_names(conn))
    finally:
        conn.close()


def test_init_db_records_current_schema_version(db_path):
    conn = init_db(db_path)
    try:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
    finally:
        conn.close()


def test_init_db_is_idempotent_and_preserves_data(db_path):
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO modules (slug, name, phase, importance, status) "
        "VALUES ('m1', 'Module One', 1, 'high', 'AVAILABLE')"
    )
    conn.commit()
    conn.close()

    # Re-open and re-init against the same file: must not error or wipe rows.
    conn2 = init_db(db_path)
    try:
        row = conn2.execute("SELECT slug FROM modules WHERE slug='m1'").fetchone()
        assert row is not None
        assert row[0] == "m1"
        assert get_schema_version(conn2) == CURRENT_SCHEMA_VERSION
    finally:
        conn2.close()


def test_foreign_keys_are_enforced(db_path):
    conn = init_db(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sources (module_id, title, type, status, "
                "resource_mode, pace_mode) "
                "VALUES (9999, 'Ghost source', 'paper', 'PROPOSED', "
                "'consumable', 'self_paced')"
            )
            conn.commit()
    finally:
        conn.close()


def test_status_events_table_has_generic_entity_columns(db_path):
    conn = init_db(db_path)
    try:
        conn.execute(
            "INSERT INTO status_events (entity_type, entity_id, from_status, "
            "to_status, reason, actor) VALUES "
            "('concept', 1, 'ACTIVE', 'USABLE', 'first application', 'user')"
        )
        conn.commit()
        row = conn.execute(
            "SELECT entity_type, entity_id, to_status FROM status_events"
        ).fetchone()
        assert row == ("concept", 1, "USABLE")
    finally:
        conn.close()
