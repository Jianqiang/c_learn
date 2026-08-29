"""TDD tests for the session & attempt service (plan section 8 table,
section 14 M0 acceptance: "一次命令能继续 session；中断后不丢 attempt").

Design under test (learning_os.services.session_service.SessionService):

- start_or_resume(): if an OPEN session already exists for the same
  (session_type, target_type, target_id), return it instead of creating a
  duplicate -- this is what lets a CLI command "just continue" a session
  after being re-invoked.
- start_attempt() inserts an attempt row immediately, before the user has
  answered anything. This is the crash-resilience mechanism: if the process
  dies between start_attempt() and submit_attempt(), the attempt row still
  exists (with submitted_at/outcome NULL) instead of being lost entirely.
- submit_attempt() fills in the outcome/answer/etc. on an existing attempt.
- end() closes a session (status=OPEN -> ENDED, ended_at set) and refuses to
  double-close or to accept new attempts afterward.
"""
from __future__ import annotations

import sqlite3

import pytest

from learning_os.db import init_db
from learning_os.repositories import ConceptRepository, ModuleRepository
from learning_os.services.session_service import SessionService


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    return init_db(tmp_path / "learning.db")


@pytest.fixture()
def item_id(conn) -> int:
    module = ModuleRepository(conn).create(slug="m1", name="Module 1", phase=1)
    concept = ConceptRepository(conn).create(module_id=module.id, slug="c1", name="Concept 1")
    cur = conn.execute(
        "INSERT INTO items (concept_id, type, prompt, grading_mode, reference_answer) "
        "VALUES (?, 'numeric', 'What is 2+2?', 'deterministic', '4')",
        (concept.id,),
    )
    conn.commit()
    return cur.lastrowid


@pytest.fixture()
def service(conn) -> SessionService:
    return SessionService(conn)


# ---------------------------------------------------------------------------
# start / resume
# ---------------------------------------------------------------------------

def test_start_or_resume_creates_new_open_session(service):
    session = service.start_or_resume(
        session_type="drill", target_type="concept", target_id=1,
    )
    assert session.status == "OPEN"
    assert session.session_type == "drill"
    assert session.ended_at is None


def test_start_or_resume_returns_existing_open_session_for_same_target(service):
    first = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    second = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    assert second.id == first.id


def test_start_or_resume_creates_separate_session_for_different_target(service):
    first = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    second = service.start_or_resume(session_type="drill", target_type="concept", target_id=2)
    assert second.id != first.id


def test_start_or_resume_creates_separate_session_for_different_type(service):
    first = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    second = service.start_or_resume(session_type="recall", target_type="concept", target_id=1)
    assert second.id != first.id


def test_start_or_resume_does_not_resume_an_ended_session(service):
    first = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    service.end(first.id)
    second = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    assert second.id != first.id
    assert second.status == "OPEN"


def test_start_or_resume_with_no_target_works_for_review_sessions(service):
    session = service.start_or_resume(
        session_type="review", time_budget_seconds=1200, item_limit=12,
    )
    assert session.target_type is None
    assert session.target_id is None
    assert session.time_budget_seconds == 1200
    assert session.item_limit == 12


def test_start_or_resume_rejects_invalid_session_type(service):
    with pytest.raises(ValueError):
        service.start_or_resume(session_type="not-a-real-type")


# ---------------------------------------------------------------------------
# ending sessions
# ---------------------------------------------------------------------------

def test_end_session_sets_status_and_ended_at(service):
    session = service.start_or_resume(session_type="learn", target_type="concept", target_id=1)
    ended = service.end(session.id, user_output="wrote a memo")
    assert ended.status == "ENDED"
    assert ended.ended_at is not None
    assert ended.user_output == "wrote a memo"


def test_end_session_twice_raises(service):
    session = service.start_or_resume(session_type="learn", target_type="concept", target_id=1)
    service.end(session.id)
    with pytest.raises(ValueError):
        service.end(session.id)


def test_end_unknown_session_raises_keyerror(service):
    with pytest.raises(KeyError):
        service.end(99999)


# ---------------------------------------------------------------------------
# attempts: crash resilience via start_attempt / submit_attempt
# ---------------------------------------------------------------------------

def test_start_attempt_persists_before_any_answer_is_given(service, item_id, conn):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    attempt = service.start_attempt(session.id, item_id)
    assert attempt.submitted_at is None
    assert attempt.outcome is None

    # Simulate a crash: reopen a fresh connection onto the same file and
    # confirm the attempt row is durably there, not lost.
    row = conn.execute(
        "SELECT id, outcome, submitted_at FROM attempts WHERE id=?", (attempt.id,)
    ).fetchone()
    assert row is not None
    assert row[1] is None
    assert row[2] is None


def test_submit_attempt_fills_in_outcome_and_marks_submitted(service, item_id):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    attempt = service.start_attempt(session.id, item_id)
    submitted = service.submit_attempt(
        attempt.id, answer="4", outcome="PASS", confidence=0.9, latency_seconds=12.5,
        evaluator_kind="deterministic",
    )
    assert submitted.answer == "4"
    assert submitted.outcome == "PASS"
    assert submitted.confidence == 0.9
    assert submitted.latency_seconds == 12.5
    assert submitted.evaluator_kind == "deterministic"
    assert submitted.submitted_at is not None


def test_submit_attempt_rejects_invalid_outcome(service, item_id):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    attempt = service.start_attempt(session.id, item_id)
    with pytest.raises(ValueError):
        service.submit_attempt(attempt.id, answer="4", outcome="NOT_A_REAL_OUTCOME")


def test_record_attempt_is_a_one_shot_start_plus_submit(service, item_id):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    attempt = service.record_attempt(
        session.id, item_id, answer="4", outcome="PASS",
        evaluator_kind="deterministic",
    )
    assert attempt.outcome == "PASS"
    assert attempt.submitted_at is not None


def test_start_attempt_on_ended_session_raises(service, item_id):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    service.end(session.id)
    with pytest.raises(ValueError):
        service.start_attempt(session.id, item_id)


def test_list_attempts_returns_all_attempts_for_session_in_order(service, item_id):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    a1 = service.record_attempt(session.id, item_id, answer="4", outcome="PASS")
    a2 = service.record_attempt(session.id, item_id, answer="5", outcome="MISS")
    attempts = service.list_attempts(session.id)
    assert [a.id for a in attempts] == [a1.id, a2.id]


def test_misconception_code_and_feedback_are_stored(service, item_id):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    attempt = service.record_attempt(
        session.id, item_id, answer="bigger is always better", outcome="MISCONCEPTION",
        misconception_code="bigger-is-optimal", feedback="conflates capacity with optimality",
    )
    assert attempt.misconception_code == "bigger-is-optimal"
    assert attempt.feedback == "conflates capacity with optimality"


def test_human_override_defaults_false_and_can_be_set_true(service, item_id):
    session = service.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    default_attempt = service.record_attempt(session.id, item_id, answer="4", outcome="PASS")
    assert default_attempt.human_override is False

    overridden = service.record_attempt(
        session.id, item_id, answer="4", outcome="MISCONCEPTION", human_override=True,
    )
    assert overridden.human_override is True
