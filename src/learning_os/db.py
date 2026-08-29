"""SQLite schema management and a minimal migration runner.

Design notes (see Personal_Learning_OS_v1_Tech_Plan.md section 7):
- SQLite holds *runtime state* (sessions, attempts, review state, status
  events). Content definitions (modules/sources/concepts/items) are seeded
  from YAML but persisted here too so the rest of the system only talks to
  one store.
- schema_migrations tracks a monotonically increasing integer version so
  future schema changes can be applied via explicit, tested migrations
  instead of ad-hoc ALTER TABLE calls scattered across the codebase.
- init_db() is idempotent: calling it against an existing file only applies
  migrations that have not yet run; it never drops or truncates tables.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

CURRENT_SCHEMA_VERSION = 2


def _migration_001_initial_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            phase INTEGER NOT NULL,
            importance TEXT,
            status TEXT NOT NULL DEFAULT 'AVAILABLE'
                CHECK (status IN ('AVAILABLE','ACTIVE','PAUSED','ARCHIVED')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL REFERENCES modules(id),
            slug TEXT UNIQUE,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            url_or_path TEXT,
            estimated_minutes INTEGER,
            priority TEXT,
            status TEXT NOT NULL DEFAULT 'PROPOSED'
                CHECK (status IN
                    ('PROPOSED','QUEUED','VISIBLE','OPEN','CONSUMED',
                     'SKIPPED','ARCHIVED')),
            resource_mode TEXT NOT NULL DEFAULT 'consumable'
                CHECK (resource_mode IN ('consumable','reference','sensor')),
            pace_mode TEXT NOT NULL DEFAULT 'self_paced'
                CHECK (pace_mode IN ('self_paced','external_paced')),
            scope_note TEXT,
            scope_confirmed INTEGER NOT NULL DEFAULT 0,
            output_hint TEXT,
            source_file TEXT,
            source_line INTEGER,
            content_hash TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL REFERENCES modules(id),
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            importance TEXT,
            workflow_status TEXT NOT NULL DEFAULT 'QUEUED'
                CHECK (workflow_status IN
                    ('QUEUED','ACTIVE','USABLE','STABLE','RETIRED',
                     'REACTIVATED')),
            description TEXT,
            research_relevance TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS focus_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            current_phase INTEGER NOT NULL DEFAULT 1,
            target_type TEXT CHECK (target_type IN ('module','concept') OR target_type IS NULL),
            target_id INTEGER,
            rationale TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS learning_outputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL REFERENCES modules(id),
            title TEXT NOT NULL,
            kind TEXT,
            phase INTEGER,
            required INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'PROPOSED'
                CHECK (status IN ('PROPOSED','ACTIVE','SUBMITTED','ARCHIVED')),
            source_file TEXT,
            source_line INTEGER,
            evidence_level TEXT CHECK (evidence_level IN ('PARTIAL','STRONG') OR evidence_level IS NULL),
            reference TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS concept_sources (
            concept_id INTEGER NOT NULL REFERENCES concepts(id),
            source_id INTEGER NOT NULL REFERENCES sources(id),
            relationship TEXT,
            notes TEXT,
            PRIMARY KEY (concept_id, source_id)
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_id INTEGER NOT NULL REFERENCES concepts(id),
            type TEXT NOT NULL
                CHECK (type IN
                    ('numeric','symbolic','discrimination','explanation',
                     'counterfactual')),
            prompt TEXT NOT NULL,
            grading_mode TEXT NOT NULL
                CHECK (grading_mode IN ('deterministic','rubric','manual')),
            reference_answer TEXT,
            rubric_json TEXT,
            answer_schema_json TEXT,
            difficulty TEXT,
            calibration_eligible INTEGER NOT NULL DEFAULT 0,
            content_version INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_type TEXT NOT NULL
                CHECK (session_type IN ('drill','learn','recall','review','apply')),
            target_type TEXT,
            target_id INTEGER,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            ended_at TEXT,
            time_budget_seconds INTEGER,
            item_limit INTEGER,
            status TEXT NOT NULL DEFAULT 'OPEN'
                CHECK (status IN ('OPEN','ENDED')),
            user_goal TEXT,
            user_output TEXT
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            item_id INTEGER NOT NULL REFERENCES items(id),
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            submitted_at TEXT,
            answer TEXT,
            outcome TEXT
                CHECK (outcome IN
                    ('PASS','PARTIAL','MISS','MISCONCEPTION','SKIPPED')
                    OR outcome IS NULL),
            confidence REAL,
            latency_seconds REAL,
            misconception_code TEXT,
            feedback TEXT,
            evaluator_kind TEXT,
            evaluator_version TEXT,
            human_override INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS review_state (
            item_id INTEGER PRIMARY KEY REFERENCES items(id),
            due_at TEXT,
            stability REAL,
            difficulty REAL,
            last_outcome TEXT,
            last_reviewed_at TEXT,
            scheduler_kind TEXT NOT NULL DEFAULT 'baseline',
            scheduler_version TEXT NOT NULL DEFAULT '1',
            active INTEGER NOT NULL DEFAULT 1,
            lapse_count INTEGER NOT NULL DEFAULT 0,
            failure_streak INTEGER NOT NULL DEFAULT 0,
            intervention_required INTEGER NOT NULL DEFAULT 0,
            suspended_until TEXT
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_id INTEGER NOT NULL REFERENCES concepts(id),
            output_id INTEGER REFERENCES learning_outputs(id),
            reference_type TEXT,
            reference TEXT,
            note TEXT,
            evidence TEXT,
            evidence_level TEXT NOT NULL
                CHECK (evidence_level IN ('PARTIAL','STRONG')),
            result TEXT NOT NULL DEFAULT 'UNASSESSED'
                CHECK (result IN ('SUCCESS','PARTIAL','FAILURE','UNASSESSED')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS status_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            reason TEXT,
            actor TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )


def _migration_002_review_state_scheduler_bookkeeping(conn: sqlite3.Connection) -> None:
    """The baseline scheduler (learning_os.schedulers.baseline) needs two
    pieces of state that migration 001 didn't persist, so a second
    record_outcome() call couldn't tell where the ladder actually was:

    - ladder_rung: current position on the 1/3/7/14/30-day ladder.
    - outcome_history: last few real outcomes (JSON array of strings),
      used for the "4-of-5 non-PASS" leech window check.

    Without these, ReviewService re-derived a fresh ReviewState(ladder_rung=0,
    outcome_history=()) from the DB row on every call, so PASS always
    scheduled 1 day out instead of advancing 1 -> 3 -> 7 -> 14 -> 30, and the
    leech window never accumulated across separate record_outcome() calls.

    Crash-recovery note (architect review, 2026-08-29): this used to be a
    single conn.executescript() running both ALTER TABLE statements, with
    schema_migrations only updated afterwards. If the process died between
    the first ALTER TABLE succeeding and the second one (or the
    schema_migrations write), the next init_db() would treat the migration
    as not-yet-applied and re-run both ALTER TABLE statements from scratch,
    crashing with "duplicate column name: ladder_rung" on the column that
    had already been added. Each ALTER TABLE is now run individually and
    guarded by a PRAGMA table_info() check, so a half-applied migration 002
    resumes and completes instead of erroring.
    """
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(review_state)")
    }
    if "ladder_rung" not in existing_columns:
        conn.execute(
            "ALTER TABLE review_state ADD COLUMN ladder_rung "
            "INTEGER NOT NULL DEFAULT 0"
        )
    if "outcome_history" not in existing_columns:
        conn.execute(
            "ALTER TABLE review_state ADD COLUMN outcome_history "
            "TEXT NOT NULL DEFAULT '[]'"
        )


# Ordered list of migrations. Each entry's index+1 is its schema version.
_MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [
    _migration_001_initial_schema,
    _migration_002_review_state_scheduler_bookkeeping,
]


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def get_schema_version(conn: sqlite3.Connection) -> int:
    _ensure_migrations_table(conn)
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return row[0] or 0


def init_db(path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite file at `path` and bring it up
    to CURRENT_SCHEMA_VERSION. Safe to call repeatedly; never drops data.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_migrations_table(conn)

    current = get_schema_version(conn)
    for version, migration in enumerate(_MIGRATIONS, start=1):
        if version > current:
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
            )
    conn.commit()
    return conn
