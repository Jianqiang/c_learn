"""CLI-layer end-to-end test for the M0 acceptance criterion (plan section
14): "新环境初始化后，可从 drill 走到 apply，SQLite 中有完整可追溯记录"
-- driven through the *actual* `learn` Typer app (CliRunner), not the
service layer directly.

Why this file exists (2026-08-30 audit finding, P0): tests/test_end_to_end.py
already proves the service layer (ConceptRepository/SessionService/
ReviewService/ApplicationService) composes correctly end-to-end. But an
independent manual run of the exact command sequence README.md's Quickstart
claimed was "smoke-tested" showed the CLI itself never actually closes the
loop:

- `learn drill` never transitions a QUEUED concept to ACTIVE.
- `learn drill`/`learn recall` attempts never update review_state at all
  (ReviewService.record_outcome() was never wired into the CLI path), so
  `learn review` always reports an empty queue no matter how many attempts
  were recorded.
- There was no CLI command reaching promote_to_usable()/promote_to_stable()
  at all -- `learn apply` only ever inserts an applications row, it never
  advances workflow_status.
- Consequently `learn retire` on a freshly-seeded concept always failed
  with "concept cannot transition from QUEUED to RETIRED", because nothing
  in the CLI path had ever moved the concept off QUEUED.

This test drives the CLI exactly the way a real user (or the README
Quickstart) would, and asserts on the resulting SQLite state after each
step, so a future regression that silently breaks the CLI closure again
(as opposed to the service layer, which test_end_to_end.py already guards)
fails here first.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from learning_os.cli import app

REAL_CONTENT_DIR = Path(__file__).resolve().parents[1] / "content"

runner = CliRunner()


def _run(db_path, *args):
    return runner.invoke(app, ["--db", str(db_path), *args])


@pytest.fixture()
def seeded_db(tmp_path):
    db_path = tmp_path / "learning.db"
    init_result = _run(db_path, "init")
    assert init_result.exit_code == 0, init_result.output
    seed_result = _run(db_path, "seed", "--content-dir", str(REAL_CONTENT_DIR))
    assert seed_result.exit_code == 0, seed_result.output
    return db_path


def _concept_status(db_path, slug: str) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT workflow_status FROM concepts WHERE slug=?", (slug,)
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def test_drill_auto_activates_a_queued_concept(seeded_db):
    assert _concept_status(seeded_db, "kv-cache") == "QUEUED"

    result = _run(seeded_db, "drill", "kv-cache", "--answer", "21.47")
    assert result.exit_code == 0, result.output

    assert _concept_status(seeded_db, "kv-cache") == "ACTIVE"


def test_drill_writes_a_review_state_row_so_review_is_not_always_empty(seeded_db):
    _run(seeded_db, "drill", "kv-cache", "--answer", "21.47")

    conn = sqlite3.connect(str(seeded_db))
    try:
        row = conn.execute(
            "SELECT rs.due_at, rs.last_outcome FROM review_state rs "
            "JOIN items i ON rs.item_id = i.id "
            "JOIN concepts c ON i.concept_id = c.id "
            "WHERE c.slug='kv-cache' AND i.reference_answer='21.47'"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None, (
        "drill never created a review_state row -- ReviewService.record_outcome() "
        "is not wired into the CLI drill path"
    )
    due_at, last_outcome = row
    assert due_at is not None
    assert last_outcome == "PASS"


def test_review_only_surfaces_an_item_once_its_due_at_has_actually_passed(seeded_db):
    """CLI-layer time-travel test for the review scheduling loop (plan 10.5).

    `learn review`'s CLI wiring (cli.py's `review` command) calls
    `ReviewService.select_batch(now=datetime.now())` with the real system
    clock and no injection point, and this project has no `freezegun`
    dependency installed. So this test can't mock time directly -- instead
    it exploits the fact that ReviewService persists `due_at` as a plain
    `"%Y-%m-%d %H:%M:%S"` string (review_service.py's `_DATE_FMT`) and
    `due_items()`'s SQL is a simple `due_at <= ?` comparison against
    whatever `now` the caller passes in. Writing a due_at string directly
    via sqlite3 is therefore equivalent to advancing the clock, without
    touching the CLI process's own `datetime.now()`.

    This closes a real gap: test_drill_writes_a_review_state_row_so_review_is_not_always_empty
    only asserts a review_state row exists with due_at IS NOT NULL. It never
    asserts (a) that a freshly-scheduled item is correctly absent from
    `learn review`'s output before its due_at, nor (b) that the exact same
    item becomes visible in `learn review`'s output once due_at is in the
    past -- i.e. that the CLI's review command is actually reading and
    respecting due_at, rather than e.g. always returning everything or
    always returning nothing.
    """
    db_path = seeded_db

    # 1. A correct drill answer records a PASS, which the baseline scheduler
    #    (schedulers/baseline.py, ladder day 1) schedules 1 day into the
    #    future from now -- not immediately due.
    result = _run(db_path, "drill", "kv-cache", "--answer", "21.47")
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(str(db_path))
    try:
        item_id = conn.execute(
            "SELECT i.id FROM items i JOIN concepts c ON i.concept_id = c.id "
            "WHERE c.slug='kv-cache' AND i.reference_answer='21.47'"
        ).fetchone()[0]
    finally:
        conn.close()

    # 2. Right after the PASS, due_at is ~1 day out, so this item must NOT
    #    be due yet. The seeded content has no other pre-existing
    #    review_state rows (those are only created by a CLI drill/recall
    #    call), so the batch should be empty.
    before = _run(db_path, "review")
    assert before.exit_code == 0, before.output
    assert "No items due for review." in before.output
    assert f"item {item_id}:" not in before.output

    # 3. Time-travel: rewrite due_at to a moment in the past, using the same
    #    "%Y-%m-%d %H:%M:%S" format ReviewService._fmt()/_parse() use, so
    #    the very next `learn review` call's real-clock `now` will compare
    #    as due_at <= now.
    from datetime import datetime, timedelta

    past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE review_state SET due_at=? WHERE item_id=?", (past, item_id)
        )
        conn.commit()
    finally:
        conn.close()

    # 4. Now that due_at has "passed", the same CLI command -- with no other
    #    change -- must surface the item with a human-readable reason.
    after = _run(db_path, "review")
    assert after.exit_code == 0, after.output
    assert "No items due for review." not in after.output
    assert f"item {item_id}: due for review" in after.output


def test_full_readme_quickstart_lifecycle_reaches_retired(seeded_db):
    """Drives the exact command sequence the README Quickstart documents
    (plus the `promote`/`repair`/`--result` additions this fix introduces)
    and asserts the concept genuinely reaches RETIRED, with every hop
    recorded in status_events -- the thing the manual audit run found does
    NOT currently happen."""
    db_path = seeded_db

    # 1. drill: QUEUED -> ACTIVE, records a PASS attempt + review_state row.
    result = _run(db_path, "drill", "kv-cache", "--answer", "21.47")
    assert result.exit_code == 0, result.output
    assert _concept_status(db_path, "kv-cache") == "ACTIVE"

    # 2. apply: record a real-application evidence row (seed already gave
    #    kv-cache one PARTIAL application per the 2026-08-30 audit's evidence
    #    honesty fix, but recording another here matches the README's
    #    documented `learn apply` step and doesn't depend on seed content).
    result = _run(db_path, "apply", "kv-cache", "--ref", "smoke test application")
    assert result.exit_code == 0, result.output

    # 3. promote ACTIVE -> USABLE: this command did not exist before this
    #    fix; promote_to_usable() was only reachable from the service layer.
    result = _run(
        db_path, "promote", "kv-cache", "--to", "usable",
        "--reason", "core rubric atom passed + evidence on file",
    )
    assert result.exit_code == 0, result.output
    assert "USABLE" in result.output
    assert _concept_status(db_path, "kv-cache") == "USABLE"

    # 4. recall: a later PASS on the same item is the delayed-recall proxy.
    result = _run(db_path, "recall", "kv-cache", "--answer", "21.47")
    assert result.exit_code == 0, result.output

    # 5. apply twice more with --result success and --strong, to satisfy
    #    promote_to_stable()'s "2 different cases + >=1 STRONG" gate. The
    #    `--result` option did not exist before this fix -- `learn apply`
    #    could only ever write result='UNASSESSED', making promote_to_stable()
    #    permanently unreachable via the CLI.
    result = _run(
        db_path, "apply", "kv-cache", "--ref", "second real case", "--strong",
        "--result", "SUCCESS",
    )
    assert result.exit_code == 0, result.output
    result = _run(
        db_path, "apply", "kv-cache", "--ref", "third real case", "--strong",
        "--result", "SUCCESS",
    )
    assert result.exit_code == 0, result.output

    # 6. promote USABLE -> STABLE.
    result = _run(
        db_path, "promote", "kv-cache", "--to", "stable",
        "--reason", "delayed recall passed, 2 distinct SUCCESS cases on file",
    )
    assert result.exit_code == 0, result.output
    assert "STABLE" in result.output
    assert _concept_status(db_path, "kv-cache") == "STABLE"

    # 7. retire STABLE -> RETIRED -- this is the exact command the manual
    #    audit run found always failing with "cannot transition from QUEUED
    #    to RETIRED" because nothing upstream had ever moved the concept.
    result = _run(db_path, "retire", "kv-cache", "--reason", "pausing active review")
    assert result.exit_code == 0, result.output
    assert "RETIRED" in result.output
    assert _concept_status(db_path, "kv-cache") == "RETIRED"

    # 8. full traceability: every hop is in status_events with a reason.
    conn = sqlite3.connect(str(db_path))
    try:
        concept_id = conn.execute(
            "SELECT id FROM concepts WHERE slug='kv-cache'"
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT from_status, to_status, reason FROM status_events "
            "WHERE entity_type='concept' AND entity_id=? ORDER BY id",
            (concept_id,),
        ).fetchall()
    finally:
        conn.close()
    transitions = [(r[0], r[1]) for r in rows]
    assert transitions == [
        ("QUEUED", "ACTIVE"),
        ("ACTIVE", "USABLE"),
        ("USABLE", "STABLE"),
        ("STABLE", "RETIRED"),
    ]
    assert all(r[2] for r in rows), "every recorded transition must carry a reason"

    # 9. export still works at the end of the full lifecycle.
    export_dir = db_path.parent / "export_out"
    result = _run(db_path, "export", "--out", str(export_dir))
    assert result.exit_code == 0, result.output
    assert (export_dir / "concepts.json").exists()


def test_repair_command_clears_a_leeched_item(seeded_db):
    """Three consecutive MISS drills on the same item trip the leech rule
    (plan 10.4); `learn repair` must be the CLI's way back onto the ladder
    -- there was no such command before this fix, so a leeched item could
    never be reviewed again via the CLI."""
    db_path = seeded_db

    for _ in range(3):
        result = _run(db_path, "drill", "kv-cache", "--answer", "0")  # wrong -> MISS
        assert result.exit_code == 0, result.output

    conn = sqlite3.connect(str(db_path))
    try:
        item_id, active, intervention = conn.execute(
            "SELECT rs.item_id, rs.active, rs.intervention_required FROM review_state rs "
            "JOIN items i ON rs.item_id = i.id "
            "JOIN concepts c ON i.concept_id = c.id "
            "WHERE c.slug='kv-cache' AND i.reference_answer='21.47'"
        ).fetchone()
    finally:
        conn.close()
    assert active == 0
    assert intervention == 1

    result = _run(db_path, "repair", "kv-cache")
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(str(db_path))
    try:
        active, intervention = conn.execute(
            "SELECT active, intervention_required FROM review_state WHERE item_id=?",
            (item_id,),
        ).fetchone()
    finally:
        conn.close()
    assert active == 1
    assert intervention == 0


def test_seed_reports_a_clean_error_and_writes_nothing_on_malformed_content(tmp_path):
    """2026-08-31 audit companion fix: seed_database() is now transactional
    (tests/test_seed_loader.py covers the rollback itself at the service
    layer), but the CLI must also surface the failure as a normal `Error:`
    message -- not a raw Python traceback -- and the caller must be able to
    trust that a failed `learn seed` left zero rows behind, without having
    to inspect the database by hand."""
    db_path = tmp_path / "learning.db"
    assert _run(db_path, "init").exit_code == 0

    content_dir = tmp_path / "bad_content"
    (content_dir / "concepts").mkdir(parents=True)
    (content_dir / "items").mkdir(parents=True)
    (content_dir / "modules.yaml").write_text(
        "modules:\n  - slug: mod-x\n    name: 'Module X'\n    phase: 1\n"
    )
    (content_dir / "sources.yaml").write_text("sources: []\n")
    (content_dir / "concepts" / "concept-x.yaml").write_text(
        "concept:\n  slug: concept-x\n  module_slug: mod-x\n  name: 'Concept X'\n"
        "sources: []\n"
    )
    # Missing the required `grading_mode` key -> KeyError deep in seed_database().
    (content_dir / "items" / "concept-x.yaml").write_text(
        "items:\n  - type: numeric\n    prompt: 'broken item'\n"
        "    reference_answer: '0'\n"
    )

    result = _run(db_path, "seed", "--content-dir", str(content_dir))

    assert result.exit_code != 0
    assert "Traceback" not in result.output, (
        "seed failure must be reported as a clean CLI error, not a raw traceback"
    )
    assert "Error:" in result.output

    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0] == 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn backup / learn restore (2026-08-31 audit finding, P2)
# ---------------------------------------------------------------------------
#
# backup_service.backup_database()/restore_database() have been implemented
# and unit-tested (tests/test_backup_export.py) since M0, but no `learn`
# command ever called them -- only `learn export` (JSON dump) was CLI-wired.
# Plan 14's M0 acceptance line "SQLite 单文件 backup 和 JSON export 的最小命令
# 可用" was therefore only half-true: the backup *service* existed, but the
# backup *command* did not. These tests drive the new `learn backup` /
# `learn restore` commands through the real CLI.

def test_backup_creates_a_dated_sqlite_file_in_the_backups_dir(seeded_db, tmp_path):
    backups_dir = tmp_path / "backups"
    result = _run(seeded_db, "backup", "--out", str(backups_dir))
    assert result.exit_code == 0, result.output

    files = list(backups_dir.glob("learning_*.db"))
    assert len(files) == 1, f"expected exactly one backup file, found {files}"

    # The backup must be a real, independently-openable SQLite file with the
    # same seeded data, not just a marker file.
    conn = sqlite3.connect(str(files[0]))
    try:
        row = conn.execute("SELECT slug FROM concepts WHERE slug='kv-cache'").fetchone()
        assert row is not None
    finally:
        conn.close()


def test_backup_defaults_out_dir_to_backups_next_to_the_db(seeded_db):
    result = _run(seeded_db, "backup")
    assert result.exit_code == 0, result.output

    default_backups_dir = seeded_db.parent / "backups"
    files = list(default_backups_dir.glob("learning_*.db"))
    assert len(files) == 1, (
        f"expected `learn backup` with no --out to default to "
        f"{default_backups_dir}, found {files}"
    )


def test_restore_recovers_a_backup_over_the_current_db(seeded_db, tmp_path):
    backups_dir = tmp_path / "backups"
    backup_result = _run(seeded_db, "backup", "--out", str(backups_dir))
    assert backup_result.exit_code == 0, backup_result.output
    backup_file = next(backups_dir.glob("learning_*.db"))

    # Drill kv-cache after the backup was taken, so current DB state now
    # differs from the backup (QUEUED -> ACTIVE).
    drill_result = _run(seeded_db, "drill", "kv-cache", "--answer", "21.47")
    assert drill_result.exit_code == 0, drill_result.output
    assert _concept_status(seeded_db, "kv-cache") == "ACTIVE"

    restore_result = _run(seeded_db, "restore", str(backup_file))
    assert restore_result.exit_code == 0, restore_result.output

    # The restored DB should reflect the pre-drill (backed-up) state again.
    assert _concept_status(seeded_db, "kv-cache") == "QUEUED"


def test_restore_rejects_a_file_that_is_not_a_learning_os_backup(seeded_db, tmp_path):
    bogus = tmp_path / "not_a_backup.db"
    bogus.write_text("this is not sqlite at all")

    result = _run(seeded_db, "restore", str(bogus))
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "Error:" in result.output


def test_restore_reports_a_clean_error_for_a_missing_backup_file(seeded_db, tmp_path):
    result = _run(seeded_db, "restore", str(tmp_path / "does_not_exist.db"))
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "Error:" in result.output
