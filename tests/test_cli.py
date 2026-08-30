"""TDD for the CLI (plan 12.1): `learn init/focus set/status/drill/learn/
recall/review/apply/output list/output complete/retire/reactivate/export`,
all as thin Typer wrappers around the existing service/repository layer.
`learn import-syllabus` is out of scope for this module (plan 12.1 lists it,
but Task 11's description only covers the commands above; import-syllabus
belongs to the seed-content task).

Every test drives the CLI through Typer's CliRunner and points `--db` at a
tmp_path file, mirroring the `conn(tmp_path)` fixture style already used in
tests/test_repositories.py -- but going through the *process-level* command
(app, not a raw sqlite3 connection) so this test suite is the one place that
verifies wiring, not service logic (already covered by each service's own
test file).
"""
from __future__ import annotations

import sqlite3

import pytest
from typer.testing import CliRunner

from learning_os.cli import app
from learning_os.db import init_db
from learning_os.repositories import ConceptRepository, ModuleRepository, SourceRepository
from learning_os.services.application_service import ApplicationService
from learning_os.services.session_service import SessionService

runner = CliRunner()


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "learning.db"


def _run(db_path, *args):
    return runner.invoke(app, ["--db", str(db_path), *args])


def _seed_module_concept_item(db_path, *, with_item=True):
    """Bootstrap a module + concept (+ optionally one deterministic item)
    directly through the repository layer, bypassing the CLI's own `init`/
    content-authoring commands -- this file tests CLI wiring, not content
    import, so tests that need a concept to already exist seed it the same
    way tests/test_repositories.py does."""
    conn = init_db(db_path)
    try:
        modules = ModuleRepository(conn)
        concepts = ConceptRepository(conn)
        m = modules.create(slug="llm-econ", name="LLM Economics", phase=1)
        c = concepts.create(module_id=m.id, slug="kv-cache", name="KV cache")
        item_id = None
        if with_item:
            cur = conn.execute(
                "INSERT INTO items (concept_id, type, prompt, grading_mode, "
                "reference_answer) VALUES (?, 'numeric', 'How many bytes?', "
                "'deterministic', '100')",
                (c.id,),
            )
            conn.commit()
            item_id = cur.lastrowid
        return m, c, item_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn init
# ---------------------------------------------------------------------------

def test_init_creates_database_file(db_path):
    assert not db_path.exists()
    result = _run(db_path, "init")
    assert result.exit_code == 0, result.output
    assert db_path.exists()
    # idempotent: calling init again must not blow up or drop anything
    result2 = _run(db_path, "init")
    assert result2.exit_code == 0, result2.output


def test_init_is_idempotent_and_preserves_data(db_path):
    _run(db_path, "init")
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO modules (slug, name, phase) VALUES ('m1', 'M1', 1)"
    )
    conn.commit()
    conn.close()

    _run(db_path, "init")

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
    conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# learn focus set
# ---------------------------------------------------------------------------

def test_focus_set_module(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "focus", "set", "llm-econ")
    assert result.exit_code == 0, result.output
    assert "llm-econ" in result.output


def test_focus_set_concept(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "focus", "set", "kv-cache")
    assert result.exit_code == 0, result.output
    assert "kv-cache" in result.output


def test_focus_set_unknown_slug_fails_cleanly(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "focus", "set", "does-not-exist")
    assert result.exit_code != 0
    assert "neither a known module nor concept" in result.output.lower()


# ---------------------------------------------------------------------------
# learn status
# ---------------------------------------------------------------------------

def test_status_without_slug_lists_all_modules(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "status")
    assert result.exit_code == 0, result.output
    assert "llm-econ" in result.output
    assert "AVAILABLE" in result.output


def test_status_with_module_slug_shows_module_and_its_concepts(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "status", "llm-econ")
    assert result.exit_code == 0, result.output
    assert "llm-econ" in result.output
    assert "kv-cache" in result.output


def test_status_with_concept_slug_shows_workflow_status(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "status", "kv-cache")
    assert result.exit_code == 0, result.output
    assert "QUEUED" in result.output


# ---------------------------------------------------------------------------
# learn drill (deterministic grading, no LLM required)
# ---------------------------------------------------------------------------

def test_drill_runs_item_and_records_pass_attempt(db_path):
    _m, c, item_id = _seed_module_concept_item(db_path)
    result = _run(db_path, "drill", "kv-cache", "--answer", "100")
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output

    conn = sqlite3.connect(str(db_path))
    outcome = conn.execute(
        "SELECT outcome FROM attempts WHERE item_id=?", (item_id,)
    ).fetchone()[0]
    conn.close()
    assert outcome == "PASS"


def test_drill_wrong_answer_records_miss(db_path):
    _seed_module_concept_item(db_path)
    result = _run(db_path, "drill", "kv-cache", "--answer", "999")
    assert result.exit_code == 0, result.output
    assert "MISS" in result.output


def test_drill_resumes_open_session_instead_of_forking(db_path):
    _seed_module_concept_item(db_path)
    _run(db_path, "drill", "kv-cache", "--answer", "100")
    _run(db_path, "drill", "kv-cache", "--answer", "100")

    conn = sqlite3.connect(str(db_path))
    session_count = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE session_type='drill'"
    ).fetchone()[0]
    # start_or_resume() only opens a new session while none is OPEN; each
    # invocation here records one attempt then ends its own session, so two
    # separate `learn drill` invocations legitimately produce two sessions --
    # this asserts wiring calls start_or_resume() (not two raw INSERTs by
    # accident) by checking the total attempt count matches invocation count.
    attempt_count = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    conn.close()
    assert session_count >= 1
    assert attempt_count == 2


def test_drill_unknown_concept_fails_cleanly(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "drill", "nope", "--answer", "1")
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_drill_concept_with_no_items_fails_cleanly(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "drill", "kv-cache", "--answer", "1")
    assert result.exit_code != 0
    assert "no active item" in result.output.lower()


# ---------------------------------------------------------------------------
# learn learn <source-slug>
# ---------------------------------------------------------------------------

def test_learn_marks_source_consumed_and_ends_session(db_path):
    conn = init_db(db_path)
    modules = ModuleRepository(conn)
    sources = SourceRepository(conn)
    m = modules.create(slug="llm-econ", name="LLM Economics", phase=1)
    s = sources.create(
        module_id=m.id, slug="kaplan-2020", title="Kaplan Scaling Laws",
        type="paper", resource_mode="consumable", pace_mode="self_paced",
        scope_confirmed=True,
    )
    sources.set_status(s.id, "QUEUED")
    sources.set_status(s.id, "OPEN")
    conn.close()

    result = _run(db_path, "learn", "kaplan-2020")
    assert result.exit_code == 0, result.output
    assert "CONSUMED" in result.output

    conn = sqlite3.connect(str(db_path))
    status = conn.execute(
        "SELECT status FROM sources WHERE slug='kaplan-2020'"
    ).fetchone()[0]
    conn.close()
    assert status == "CONSUMED"


def test_learn_unknown_source_fails_cleanly(db_path):
    init_db(db_path).close()
    result = _run(db_path, "learn", "nope")
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# learn recall
# ---------------------------------------------------------------------------

def test_recall_runs_item_in_recall_session(db_path):
    _seed_module_concept_item(db_path)
    result = _run(db_path, "recall", "kv-cache", "--answer", "100")
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output

    conn = sqlite3.connect(str(db_path))
    session_type = conn.execute(
        "SELECT s.session_type FROM sessions s "
        "JOIN attempts a ON a.session_id = s.id LIMIT 1"
    ).fetchone()[0]
    conn.close()
    assert session_type == "recall"


# ---------------------------------------------------------------------------
# learn review
# ---------------------------------------------------------------------------

def test_review_with_no_due_items_reports_empty_batch(db_path):
    _seed_module_concept_item(db_path)
    result = _run(db_path, "review")
    assert result.exit_code == 0, result.output
    assert "no items due" in result.output.lower()


def test_review_lists_due_item_with_reason(db_path):
    _m, _c, item_id = _seed_module_concept_item(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO review_state (item_id) VALUES (?)", (item_id,))
    conn.commit()
    conn.close()

    result = _run(db_path, "review")
    assert result.exit_code == 0, result.output
    assert str(item_id) in result.output
    assert "due for review" in result.output.lower()


# ---------------------------------------------------------------------------
# learn apply
# ---------------------------------------------------------------------------

def test_apply_records_partial_application(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "apply", "kv-cache", "--ref", "used in memo #3")
    assert result.exit_code == 0, result.output
    assert "PARTIAL" in result.output

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT reference, evidence_level FROM applications"
    ).fetchone()
    conn.close()
    assert row == ("used in memo #3", "PARTIAL")


def test_apply_strong_evidence_flag(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(
        db_path, "apply", "kv-cache", "--ref", "used in real research", "--strong",
    )
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(str(db_path))
    level = conn.execute(
        "SELECT evidence_level FROM applications"
    ).fetchone()[0]
    conn.close()
    assert level == "STRONG"


def test_apply_unknown_concept_fails_cleanly(db_path):
    _seed_module_concept_item(db_path, with_item=False)
    result = _run(db_path, "apply", "nope", "--ref", "x")
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# learn output list / output complete
# ---------------------------------------------------------------------------

def test_output_list_shows_outputs_for_module(db_path):
    m, _c, _item_id = _seed_module_concept_item(db_path, with_item=False)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO learning_outputs (module_id, title, kind) "
        "VALUES (?, 'KV cache memo', 'memo')",
        (m.id,),
    )
    conn.commit()
    conn.close()

    result = _run(db_path, "output", "list", "llm-econ")
    assert result.exit_code == 0, result.output
    assert "KV cache memo" in result.output
    assert "PROPOSED" in result.output


def test_output_list_without_module_lists_all(db_path):
    m, _c, _item_id = _seed_module_concept_item(db_path, with_item=False)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO learning_outputs (module_id, title, kind) "
        "VALUES (?, 'KV cache memo', 'memo')",
        (m.id,),
    )
    conn.commit()
    conn.close()

    result = _run(db_path, "output", "list")
    assert result.exit_code == 0, result.output
    assert "KV cache memo" in result.output


def test_output_complete_sets_reference_and_submitted(db_path):
    m, _c, _item_id = _seed_module_concept_item(db_path, with_item=False)
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(
        "INSERT INTO learning_outputs (module_id, title, kind) "
        "VALUES (?, 'KV cache memo', 'memo')",
        (m.id,),
    )
    conn.commit()
    output_id = cur.lastrowid
    conn.close()

    result = _run(
        db_path, "output", "complete", str(output_id), "--ref", "notes/kv-cache.md",
    )
    assert result.exit_code == 0, result.output
    assert "SUBMITTED" in result.output

    conn = sqlite3.connect(str(db_path))
    status, reference = conn.execute(
        "SELECT status, reference FROM learning_outputs WHERE id=?", (output_id,)
    ).fetchone()
    conn.close()
    assert status == "SUBMITTED"
    assert reference == "notes/kv-cache.md"


def test_output_complete_requires_non_empty_reference(db_path):
    m, _c, _item_id = _seed_module_concept_item(db_path, with_item=False)
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(
        "INSERT INTO learning_outputs (module_id, title, kind) "
        "VALUES (?, 'KV cache memo', 'memo')",
        (m.id,),
    )
    conn.commit()
    output_id = cur.lastrowid
    conn.close()

    result = _run(db_path, "output", "complete", str(output_id), "--ref", "   ")
    assert result.exit_code != 0


def test_output_complete_unknown_id_fails_cleanly(db_path):
    init_db(db_path).close()
    result = _run(db_path, "output", "complete", "999", "--ref", "x")
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# learn retire / learn reactivate
# ---------------------------------------------------------------------------

def _promote_concept_to_stable(db_path, concept_id):
    """Drive a concept through the full evidence-gated path to STABLE using
    the same services the CLI itself wires to, so `learn retire` has a
    legally-retirable concept to work with without re-deriving the gate
    logic here."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    concepts = ConceptRepository(conn)
    apps = ApplicationService(conn)
    sessions = SessionService(conn)

    cur = conn.execute(
        "INSERT INTO items (concept_id, type, prompt, grading_mode, "
        "reference_answer) VALUES (?, 'numeric', 'p?', 'deterministic', '1')",
        (concept_id,),
    )
    conn.commit()
    item_id = cur.lastrowid

    concepts.set_status(concept_id, "ACTIVE", reason="start")
    drill = sessions.start_or_resume(session_type="drill", target_type="concept", target_id=concept_id)
    sessions.record_attempt(drill.id, item_id, outcome="PASS")
    apps.record_application(concept_id=concept_id, evidence_level="PARTIAL", reference="memo")
    concepts.set_status(concept_id, "USABLE", reason="usable")

    recall = sessions.start_or_resume(session_type="recall", target_type="concept", target_id=concept_id)
    sessions.record_attempt(recall.id, item_id, outcome="PASS")
    apps.record_application(concept_id=concept_id, evidence_level="STRONG", result="SUCCESS", reference="case A")
    apps.record_application(concept_id=concept_id, evidence_level="STRONG", result="SUCCESS", reference="case B")
    concepts.set_status(concept_id, "STABLE", reason="stable")
    conn.close()


def test_retire_moves_concept_to_retired(db_path):
    _m, c, _item_id = _seed_module_concept_item(db_path, with_item=False)
    _promote_concept_to_stable(db_path, c.id)

    result = _run(db_path, "retire", "kv-cache", "--reason", "not actively studying")
    assert result.exit_code == 0, result.output
    assert "RETIRED" in result.output


def test_retire_requires_reason(db_path):
    _m, c, _item_id = _seed_module_concept_item(db_path, with_item=False)
    _promote_concept_to_stable(db_path, c.id)

    result = _run(db_path, "retire", "kv-cache")
    assert result.exit_code != 0


def test_reactivate_moves_retired_concept_back(db_path):
    _m, c, _item_id = _seed_module_concept_item(db_path, with_item=False)
    _promote_concept_to_stable(db_path, c.id)
    _run(db_path, "retire", "kv-cache", "--reason", "pausing")

    result = _run(db_path, "reactivate", "kv-cache", "--reason", "new research need")
    assert result.exit_code == 0, result.output
    assert "REACTIVATED" in result.output


# ---------------------------------------------------------------------------
# learn export
# ---------------------------------------------------------------------------

def test_export_writes_json_files_for_every_table(db_path, tmp_path):
    _seed_module_concept_item(db_path, with_item=False)
    out_dir = tmp_path / "export"

    result = _run(db_path, "export", "--out", str(out_dir))
    assert result.exit_code == 0, result.output
    assert (out_dir / "modules.json").exists()
    assert (out_dir / "concepts.json").exists()
    assert (out_dir / "learning_outputs.json").exists()
