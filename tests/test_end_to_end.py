"""End-to-end integration test for the M0 acceptance criterion (plan section
14): "新环境初始化后，可从 drill 走到 apply，SQLite 中有完整可追溯记录"
(from a freshly initialized environment, the user can go from drill all the
way to apply, and SQLite holds a complete, traceable record).

This test deliberately exercises the *service layer* directly (ConceptRepository
/ ItemRepository / SessionService / ReviewService / ApplicationService) rather
than the CLI (Typer) layer, for two reasons:

1. It can assert on precise intermediate state (status_events rows, attempts
   rows, review_state transitions) that a CliRunner stdout-string test cannot
   easily pin down without becoming brittle against cosmetic output changes.
2. Every one of those services is itself unit-tested against CLI wiring in
   tests/test_cli.py already: this test's job is to prove the services
   compose correctly end-to-end against the *real* content/ vertical slice,
   not to re-test CLI argument parsing.

It seeds from the actual repo-root content/ directory (not a synthetic
fixture), the same real vertical-slice data plan 5.3 describes and that
tests/test_seed_loader.py's test_seed_database_real_content_dir_loads_cleanly
already locks to modules_created=3, concepts_created=7,
10<=items_created<=15, applications_created=2 -- so this test can safely
seed from content/ without re-deriving those bounds itself.

Flow covered (plan section 14 M0 acceptance path):
    init -> seed -> drill (ACTIVE) -> leech + repair (review) ->
    recall -> apply (promote_to_usable) -> review due-item selection ->
    apply (2 SUCCESS cases) -> promote_to_stable -> retire

Each step's persisted row(s) are asserted directly against SQLite so the
"完整可追溯记录" (complete traceable record) requirement is checked, not just
that no exception was raised.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from learning_os.db import init_db
from learning_os.repositories import ConceptRepository, ItemRepository
from learning_os.services.application_service import ApplicationService
from learning_os.services.review_service import ReviewService
from learning_os.services.seed_loader import seed_database
from learning_os.services.session_service import SessionService

REAL_CONTENT_DIR = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture()
def conn(tmp_path):
    c = init_db(tmp_path / "learning.db")
    yield c
    c.close()


@pytest.fixture()
def seeded(conn):
    """Seed the real content/ vertical slice and return (conn, seed_result)."""
    result = seed_database(conn, REAL_CONTENT_DIR)
    return conn, result


def test_seed_from_real_content_matches_locked_vertical_slice_bounds(seeded):
    """Sanity check reusing the bounds tests/test_seed_loader.py already
    locks for the real content/ directory, so a silent content/ drift would
    fail loudly here too, before the rest of this test's flow even starts."""
    _conn, result = seeded
    assert result.modules_created == 3
    assert result.concepts_created == 7
    assert 10 <= result.items_created <= 15
    assert result.applications_created == 2


def test_full_drill_to_retire_lifecycle_leaves_traceable_sqlite_record(seeded):
    conn, _seed_result = seeded
    concepts = ConceptRepository(conn)
    items = ItemRepository(conn)
    sessions = SessionService(conn)
    reviews = ReviewService(conn)
    applications = ApplicationService(conn)

    concept = concepts.get_by_slug("kv-cache")
    assert concept.workflow_status == "QUEUED"

    concept_items = items.list_by_concept(concept.id)
    # content/items/kv-cache.yaml seeds exactly 2 numeric items (21.47 GB
    # KV cache size, and the 4x batch-scaling multiplier).
    assert len(concept_items) == 2
    item = next(i for i in concept_items if i.reference_answer == "21.47")

    # -- 1. QUEUED -> ACTIVE (learner starts working the concept) ----------
    concepts.set_status(concept.id, "ACTIVE", reason="starting kv-cache drill")
    concept = concepts.get(concept.id)
    assert concept.workflow_status == "ACTIVE"

    # -- 2. drill session: first attempt is correct (PASS) ------------------
    drill_session = sessions.start_or_resume(
        session_type="drill", target_type="concept", target_id=concept.id,
    )
    assert drill_session.status == "OPEN"
    first_attempt = sessions.record_attempt(
        drill_session.id, item.id,
        answer="21.47", outcome="PASS", evaluator_kind="deterministic",
    )
    assert first_attempt.outcome == "PASS"
    assert first_attempt.submitted_at is not None

    # Resuming the same (session_type, target_type, target_id) while still
    # OPEN must return the *same* session row, not fork a new one (plan
    # section 8: "一次命令能继续 session").
    resumed = sessions.start_or_resume(
        session_type="drill", target_type="concept", target_id=concept.id,
    )
    assert resumed.id == drill_session.id
    sessions.end(drill_session.id)
    assert sessions.get_session(drill_session.id).status == "ENDED"

    # -- 3. review scheduling: three MISS attempts trigger the leech rule --
    # (plan 10.4: 3 consecutive MISS/MISCONCEPTION outcomes -> intervention
    # required, active=False, auto-scheduling paused until confirm_repair()).
    review_session = sessions.start_or_resume(
        session_type="review", target_type="concept", target_id=concept.id,
    )
    now = datetime(2026, 8, 29, 9, 0, 0)
    for i in range(3):
        sessions.record_attempt(
            review_session.id, item.id,
            answer="wrong", outcome="MISS", evaluator_kind="deterministic",
        )
        now = now + timedelta(hours=1)
        state = reviews.record_outcome(item.id, outcome="MISS", now=now)
    sessions.end(review_session.id)

    assert state.intervention_required is True
    assert state.active is False
    assert state.failure_streak == 3

    # A leeched item cannot be scheduled again until repaired.
    with pytest.raises(ValueError):
        reviews.record_outcome(item.id, outcome="MISS", now=now)

    # -- 4. confirm_repair(): the only sanctioned way back onto the ladder --
    repaired = reviews.confirm_repair(item.id, now=now)
    assert repaired.active is True
    assert repaired.intervention_required is False
    assert repaired.failure_streak == 0
    assert repaired.ladder_rung == 0

    # -- 5. recall session: a later PASS satisfies the "delayed recall
    # 通过" evidence-gate proxy for STABLE ------------------------------
    recall_session = sessions.start_or_resume(
        session_type="recall", target_type="concept", target_id=concept.id,
    )
    sessions.record_attempt(
        recall_session.id, item.id,
        answer="21.47", outcome="PASS", evaluator_kind="deterministic",
    )
    sessions.end(recall_session.id)
    now = now + timedelta(days=3)
    reviews.record_outcome(item.id, outcome="PASS", now=now)

    # -- 6. apply: promote ACTIVE -> USABLE ----------------------------------
    # The seeded content/applications.yaml already gives kv-cache one
    # STRONG application (the real CXMT capacity-planning research note), so
    # _has_any_application() is already satisfied by seed data alone; the
    # rubric-atom-pass proxy is satisfied by the PASS attempts recorded above.
    usable = applications.promote_to_usable(concept.id, reason="core rubric atom passed + evidence on file")
    assert usable.workflow_status == "USABLE"

    # -- 7. review due-item selection surfaces this item for a review batch -
    due_now = now + timedelta(days=1)
    batch = reviews.select_batch(now=due_now, active_concept_ids={concept.id})
    assert any(selected.item_id == item.id for selected in batch)
    picked = next(s for s in batch if s.item_id == item.id)
    assert "ACTIVE concept" in picked.reason

    # -- 8. apply: record two more real applications with SUCCESS results,
    # so promote_to_stable()'s "2 个不同 case 正确调用" proxy is satisfied
    # without needing the user_confirms_stable escape hatch --------------
    applications.record_application(
        concept_id=concept.id, evidence_level="STRONG",
        reference_type="research_note",
        reference="第二次真实应用：为另一客户的 batch=8 假设复核显存占用估算。",
        result="SUCCESS",
    )
    applications.record_application(
        concept_id=concept.id, evidence_level="STRONG",
        reference_type="research_note",
        reference="第三次真实应用：验证 dtype 从 bf16 切到 fp8 后的显存降幅估算。",
        result="SUCCESS",
    )

    # -- 9. promote USABLE -> STABLE -----------------------------------------
    stable = applications.promote_to_stable(concept.id, reason="delayed recall passed, 2 SUCCESS cases on file")
    assert stable.workflow_status == "STABLE"

    # -- 10. retire STABLE -> RETIRED -----------------------------------------
    retired = applications.retire(concept.id, reason="pausing active review; revisit if CXMT capex thesis resumes")
    assert retired.workflow_status == "RETIRED"

    # -- 11. full traceability: status_events records every transition in
    # order, with reasons, for this concept -----------------------------
    rows = conn.execute(
        "SELECT from_status, to_status, reason FROM status_events "
        "WHERE entity_type='concept' AND entity_id=? ORDER BY id",
        (concept.id,),
    ).fetchall()
    transitions = [(r[0], r[1]) for r in rows]
    assert transitions == [
        ("QUEUED", "ACTIVE"),
        ("ACTIVE", "USABLE"),
        ("USABLE", "STABLE"),
        ("STABLE", "RETIRED"),
    ]
    assert all(r[2] for r in rows), "every recorded transition must carry a reason"

    # -- 12. full traceability: every attempt made above is a durable,
    # individually-inspectable row (session linkage, outcome, evaluator) --
    attempt_rows = conn.execute(
        "SELECT a.outcome, s.session_type FROM attempts a "
        "JOIN sessions s ON a.session_id = s.id "
        "WHERE a.item_id=? ORDER BY a.id",
        (item.id,),
    ).fetchall()
    outcomes_by_session_type = [(row[0], row[1]) for row in attempt_rows]
    assert outcomes_by_session_type == [
        ("PASS", "drill"),
        ("MISS", "review"),
        ("MISS", "review"),
        ("MISS", "review"),
        ("PASS", "recall"),
    ]

    # -- 13. full traceability: applications table holds all 3 evidence
    # records for this concept (1 seeded + 2 recorded above), and the
    # seeded source rows this concept links to keep their source_file/
    # source_line provenance from content/sources.yaml --------------------
    # content/applications.yaml's seed row for kv-cache is evidence_level=
    # PARTIAL (2026-08-30 audit: downgraded from STRONG because it is an
    # unverified personal research recollection with no locatable
    # episode/file artifact -- see content/applications.yaml's header
    # comment). The two applications recorded live above in this test
    # (step 8) are STRONG and are what actually satisfies
    # promote_to_stable()'s "at least one STRONG application" gate.
    application_rows = applications.list_applications(concept.id)
    assert len(application_rows) == 3
    assert sum(1 for a in application_rows if a.result == "SUCCESS") == 2
    assert sum(1 for a in application_rows if a.evidence_level == "STRONG") == 2
    assert sum(1 for a in application_rows if a.evidence_level == "PARTIAL") == 1

    source_rows = conn.execute(
        "SELECT src.source_file, src.source_line FROM sources src "
        "JOIN concept_sources cs ON cs.source_id = src.id "
        "WHERE cs.concept_id=?",
        (concept.id,),
    ).fetchall()
    assert len(source_rows) >= 1
    assert all(row[0] and row[1] for row in source_rows), (
        "every source linked from the real content/ vertical slice must "
        "keep its source_file/source_line provenance (plan 7.2 #sources)"
    )
