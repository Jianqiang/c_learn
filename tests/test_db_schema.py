"""Tests for schema creation and the migration runner.

TDD focus: given a fresh SQLite file, init_db() must create every table listed
in the tech plan (section 7.2), record the schema version, and be safe to call
repeatedly (idempotent) without dropping data or raising errors.
"""
import sqlite3

import pytest

from learning_os.db import (
    CURRENT_SCHEMA_VERSION,
    _migration_001_initial_schema,
    get_schema_version,
    init_db,
)

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


# ---------------------------------------------------------------------------
# Real v1 -> v2 upgrade path (architect review: prior tests only ever built
# a fresh DB straight to v2, never exercised init_db() actually upgrading an
# existing v1 database on disk).
# ---------------------------------------------------------------------------

def _build_v1_database(db_path) -> None:
    """Construct a database at exactly schema v1: apply only migration 001
    (no ladder_rung/outcome_history columns on review_state yet) and record
    schema_migrations version=1, bypassing init_db() so this fixture stays
    correct even if init_db()'s own migration list changes.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    _migration_001_initial_schema(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, "
        "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.execute("INSERT INTO schema_migrations (version) VALUES (1)")
    conn.commit()
    conn.close()


def _seed_v1_review_state_row(db_path) -> None:
    """Insert one real, pre-existing review_state row (plus its module/
    concept/item parents) using only v1 columns, so the upgrade test can
    assert this data survives the v1->v2 migration untouched.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO modules (slug, name, phase, status) "
        "VALUES ('m1', 'Module One', 1, 'AVAILABLE')"
    )
    conn.execute(
        "INSERT INTO concepts (module_id, slug, name) VALUES (1, 'c1', 'Concept One')"
    )
    conn.execute(
        "INSERT INTO items (concept_id, type, prompt, grading_mode, reference_answer) "
        "VALUES (1, 'numeric', 'q', 'deterministic', '1')"
    )
    conn.execute(
        "INSERT INTO review_state "
        "(item_id, due_at, last_outcome, active, lapse_count, failure_streak) "
        "VALUES (1, '2026-01-05 00:00:00', 'PASS', 1, 0, 0)"
    )
    conn.commit()
    conn.close()


def test_v1_database_has_no_ladder_columns_before_upgrade(db_path):
    """Sanity check that the v1 fixture really is v1 (no v2 columns yet),
    so the upgrade assertions below are testing a real transition and not
    a database that was already at v2."""
    _build_v1_database(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(review_state)")}
        assert "ladder_rung" not in columns
        assert "outcome_history" not in columns
        assert get_schema_version(conn) == 1
    finally:
        conn.close()


def test_init_db_upgrades_v1_database_to_current_version(db_path):
    _build_v1_database(db_path)
    _seed_v1_review_state_row(db_path)

    conn = init_db(db_path)
    try:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION

        columns = {row[1] for row in conn.execute("PRAGMA table_info(review_state)")}
        assert "ladder_rung" in columns
        assert "outcome_history" in columns

        row = conn.execute(
            "SELECT item_id, due_at, last_outcome, active, ladder_rung, "
            "outcome_history FROM review_state WHERE item_id=1"
        ).fetchone()
        # Pre-existing v1 data must survive the upgrade untouched...
        assert row[0] == 1
        assert row[1] == "2026-01-05 00:00:00"
        assert row[2] == "PASS"
        assert row[3] == 1
        # ...and the new v2 columns must backfill to sane defaults rather
        # than NULL, since ReviewService reads them on every load.
        assert row[4] == 0  # ladder_rung default
        assert row[5] == "[]"  # outcome_history default
    finally:
        conn.close()


def test_init_db_upgrade_is_idempotent_on_second_call(db_path):
    """Upgrading v1->v2 must not re-run if called twice, and must not
    disturb data added after the first upgrade."""
    _build_v1_database(db_path)
    _seed_v1_review_state_row(db_path)

    conn = init_db(db_path)
    conn.execute(
        "UPDATE review_state SET ladder_rung=2 WHERE item_id=1"
    )
    conn.commit()
    conn.close()

    conn2 = init_db(db_path)
    try:
        assert get_schema_version(conn2) == CURRENT_SCHEMA_VERSION
        row = conn2.execute(
            "SELECT ladder_rung FROM review_state WHERE item_id=1"
        ).fetchone()
        # Second init_db() call must not re-run migration 002 (which would
        # error on "duplicate column" or, if guarded, would be a silent
        # no-op) nor reset ladder_rung back to its default.
        assert row[0] == 2
    finally:
        conn2.close()


def test_init_db_recovers_from_a_crash_mid_migration_002(db_path):
    """Architect review repro: migration 002 originally ran both ALTER
    TABLE statements via executescript() and only wrote
    schema_migrations(version=2) afterwards. If the process died between
    "first ALTER TABLE succeeded" and "schema_migrations updated" -- e.g.
    ladder_rung got added but outcome_history and the version bump did
    not -- the next init_db() would re-run migration 002 from scratch and
    crash with "duplicate column name: ladder_rung" instead of finishing
    the upgrade.

    Simulate exactly that half-applied state by hand (ladder_rung present,
    outcome_history absent, schema_migrations still at 1), then verify
    init_db() completes the upgrade instead of raising.
    """
    _build_v1_database(db_path)
    _seed_v1_review_state_row(db_path)

    # Hand-apply only the first half of migration 002, without recording
    # schema_migrations version=2 -- this is the "crashed mid-migration"
    # state.
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "ALTER TABLE review_state ADD COLUMN ladder_rung INTEGER NOT NULL DEFAULT 0"
    )
    conn.commit()
    conn.close()

    # Must not raise "duplicate column name: ladder_rung".
    conn2 = init_db(db_path)
    try:
        assert get_schema_version(conn2) == CURRENT_SCHEMA_VERSION
        columns = {row[1] for row in conn2.execute("PRAGMA table_info(review_state)")}
        assert "ladder_rung" in columns
        assert "outcome_history" in columns
        row = conn2.execute(
            "SELECT last_outcome, ladder_rung, outcome_history "
            "FROM review_state WHERE item_id=1"
        ).fetchone()
        # Original v1 data (and the half-applied ladder_rung default)
        # must still be intact after recovery.
        assert row[0] == "PASS"
        assert row[1] == 0
        assert row[2] == "[]"
    finally:
        conn2.close()
