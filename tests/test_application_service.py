"""TDD for the application service (plan section 6.4 evidence gates, section
7.2 #applications table, section 8 services table).

ApplicationService has two jobs:

1. record_application(): persist a real research/case application (STRONG
   evidence) or a syllabus-output-backed application (PARTIAL evidence) into
   the `applications` table.
2. promote_to_usable() / promote_to_stable() / retire() / reactivate(): the
   *only* sanctioned way to move a concept across USABLE/STABLE/RETIRED/
   REACTIVATED, because each one enforces the plan 6.4 evidence gate before
   delegating to ConceptRepository.set_status() -- a concept must never
   silently become USABLE/STABLE just because someone called set_status()
   directly with no evidence behind it.

Gate semantics under test (see application_service.py module docstring for
the full rationale of each proxy):

USABLE = >=1 attempt with outcome PASS/PARTIAL on one of the concept's items
         (proxy for "a core rubric atom passed")
         + >=1 applications row for the concept (any evidence_level).

STABLE = >=1 attempt with outcome=PASS on a `recall`-session item
         (proxy for "delayed recall passed")
         + (>=2 applications with result='SUCCESS', OR user_confirms_stable=True)
         + no item's most-recently-submitted attempt is still MISCONCEPTION
         + >=1 applications row with evidence_level='STRONG'.

RETIRED = caller must supply a non-empty reason (proxy for explicit user
          confirmation -- plan 6.3 forbids silent transitions).

REACTIVATED = no additional gate; plain adjacency-checked delegation.
"""
from __future__ import annotations

import sqlite3

import pytest

from learning_os.db import init_db
from learning_os.repositories import ConceptRepository, InvalidTransitionError, ModuleRepository
from learning_os.services.application_service import (
    ApplicationService,
    EvidenceGateError,
)
from learning_os.services.session_service import SessionService


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    return init_db(tmp_path / "learning.db")


@pytest.fixture()
def concept_id(conn) -> int:
    module = ModuleRepository(conn).create(slug="m1", name="Module 1", phase=1)
    concept = ConceptRepository(conn).create(module_id=module.id, slug="c1", name="Concept 1")
    return concept.id


@pytest.fixture()
def active_concept_id(conn, concept_id) -> int:
    ConceptRepository(conn).set_status(concept_id, "ACTIVE", reason="starting")
    return concept_id


@pytest.fixture()
def item_id(conn, active_concept_id) -> int:
    cur = conn.execute(
        "INSERT INTO items (concept_id, type, prompt, grading_mode, reference_answer) "
        "VALUES (?, 'numeric', 'What is 2+2?', 'deterministic', '4')",
        (active_concept_id,),
    )
    conn.commit()
    return cur.lastrowid


@pytest.fixture()
def sessions(conn) -> SessionService:
    return SessionService(conn)


@pytest.fixture()
def service(conn) -> ApplicationService:
    return ApplicationService(conn)


def _pass_a_rubric_atom(sessions: SessionService, item_id: int, outcome: str = "PASS") -> None:
    session = sessions.start_or_resume(session_type="drill", target_type="concept", target_id=1)
    sessions.record_attempt(session.id, item_id, answer="4", outcome=outcome)


def _pass_delayed_recall(sessions: SessionService, item_id: int) -> None:
    session = sessions.start_or_resume(session_type="recall", target_type="concept", target_id=1)
    sessions.record_attempt(session.id, item_id, answer="4", outcome="PASS")


def _record_misconception(sessions: SessionService, item_id: int) -> None:
    session = sessions.start_or_resume(session_type="drill", target_type="concept", target_id=2)
    sessions.record_attempt(
        session.id, item_id, answer="wrong", outcome="MISCONCEPTION",
        misconception_code="bad-model",
    )


def _repair_misconception(sessions: SessionService, item_id: int) -> None:
    session = sessions.start_or_resume(session_type="drill", target_type="concept", target_id=3)
    sessions.record_attempt(session.id, item_id, answer="4", outcome="PASS")


# ---------------------------------------------------------------------------
# record_application()
# ---------------------------------------------------------------------------

def test_record_strong_application_from_real_research(service, concept_id):
    app = service.record_application(
        concept_id=concept_id,
        evidence_level="STRONG",
        reference_type="research",
        reference="co_investor episode 56f725e1",
        note="used KV cache math to size a batching assumption",
        result="SUCCESS",
    )
    assert app.evidence_level == "STRONG"
    assert app.result == "SUCCESS"
    assert app.output_id is None
    fetched = service.get_application(app.id)
    assert fetched.reference == "co_investor episode 56f725e1"


def test_record_partial_application_from_syllabus_output(conn, service, active_concept_id):
    cur = conn.execute(
        "INSERT INTO learning_outputs (module_id, title, kind) "
        "VALUES ((SELECT module_id FROM concepts WHERE id=?), 'notebook', 'notebook')",
        (active_concept_id,),
    )
    conn.commit()
    output_id = cur.lastrowid

    app = service.record_application(
        concept_id=active_concept_id,
        evidence_level="PARTIAL",
        output_id=output_id,
        note="wrote the declared notebook, no real transfer yet",
    )
    assert app.evidence_level == "PARTIAL"
    assert app.output_id == output_id


def test_record_application_rejects_invalid_evidence_level(service, concept_id):
    with pytest.raises(ValueError):
        service.record_application(concept_id=concept_id, evidence_level="WEAK")


def test_record_application_rejects_invalid_result(service, concept_id):
    with pytest.raises(ValueError):
        service.record_application(
            concept_id=concept_id, evidence_level="STRONG", result="NOT_A_RESULT",
        )


def test_record_application_rejects_output_id_with_strong_evidence(service, concept_id):
    # A syllabus output is partial evidence by construction (plan 6.4); a
    # STRONG (real research/case) claim must not ride along with an
    # output_id, or it silently launders a syllabus deliverable into "real
    # transfer" evidence.
    with pytest.raises(ValueError):
        service.record_application(
            concept_id=concept_id, evidence_level="STRONG", output_id=1,
        )


def test_record_application_rejects_unknown_concept(service):
    with pytest.raises(KeyError):
        service.record_application(concept_id=99999, evidence_level="STRONG")


def test_list_applications_returns_all_for_concept_in_order(service, concept_id):
    a1 = service.record_application(concept_id=concept_id, evidence_level="STRONG")
    a2 = service.record_application(concept_id=concept_id, evidence_level="PARTIAL")
    apps = service.list_applications(concept_id)
    assert [a.id for a in apps] == [a1.id, a2.id]


# ---------------------------------------------------------------------------
# promote_to_usable(): ACTIVE -> USABLE evidence gate
# ---------------------------------------------------------------------------

def test_promote_to_usable_requires_rubric_atom_pass(
    service, active_concept_id, item_id,
):
    service.record_application(concept_id=active_concept_id, evidence_level="PARTIAL")
    with pytest.raises(EvidenceGateError):
        service.promote_to_usable(active_concept_id)
    # rejected gate check must not mutate concept state
    concept = ConceptRepository(service._conn).get(active_concept_id)
    assert concept.workflow_status == "ACTIVE"


def test_promote_to_usable_requires_evidence_record(
    service, sessions, active_concept_id, item_id,
):
    _pass_a_rubric_atom(sessions, item_id)
    with pytest.raises(EvidenceGateError):
        service.promote_to_usable(active_concept_id)


def test_promote_to_usable_succeeds_with_atom_pass_and_partial_evidence(
    service, sessions, conn, active_concept_id, item_id,
):
    _pass_a_rubric_atom(sessions, item_id, outcome="PARTIAL")
    service.record_application(concept_id=active_concept_id, evidence_level="PARTIAL")

    concept = service.promote_to_usable(
        active_concept_id, reason="passed rubric atom + partial evidence",
    )
    assert concept.workflow_status == "USABLE"

    events = conn.execute(
        "SELECT from_status, to_status, reason FROM status_events "
        "WHERE entity_type='concept' AND entity_id=? ORDER BY id",
        (active_concept_id,),
    ).fetchall()
    assert tuple(events[-1]) == (
        "ACTIVE", "USABLE", "passed rubric atom + partial evidence",
    )


def test_promote_to_usable_from_wrong_state_raises_invalid_transition(
    service, concept_id,
):
    # concept_id fixture is still QUEUED, not ACTIVE.
    with pytest.raises(InvalidTransitionError):
        service.promote_to_usable(concept_id)


# ---------------------------------------------------------------------------
# promote_to_stable(): USABLE -> STABLE evidence gate
# ---------------------------------------------------------------------------

@pytest.fixture()
def usable_concept_id(service, sessions, active_concept_id, item_id) -> int:
    _pass_a_rubric_atom(sessions, item_id)
    service.record_application(concept_id=active_concept_id, evidence_level="PARTIAL")
    service.promote_to_usable(active_concept_id, reason="usable now")
    return active_concept_id


def test_promote_to_stable_requires_delayed_recall_pass(
    service, usable_concept_id,
):
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    with pytest.raises(EvidenceGateError):
        service.promote_to_stable(usable_concept_id)


def test_promote_to_stable_requires_two_cases_or_confirmation(
    service, sessions, item_id, usable_concept_id,
):
    _pass_delayed_recall(sessions, item_id)
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    with pytest.raises(EvidenceGateError):
        service.promote_to_stable(usable_concept_id)


def test_promote_to_stable_user_confirmation_bypasses_case_count(
    service, sessions, item_id, usable_concept_id,
):
    _pass_delayed_recall(sessions, item_id)
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    concept = service.promote_to_stable(
        usable_concept_id, user_confirms_stable=True, reason="user says stable enough",
    )
    assert concept.workflow_status == "STABLE"


def test_promote_to_stable_blocked_by_unresolved_misconception(
    service, sessions, item_id, usable_concept_id,
):
    _pass_delayed_recall(sessions, item_id)
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    _record_misconception(sessions, item_id)

    with pytest.raises(EvidenceGateError):
        service.promote_to_stable(usable_concept_id)


def test_promote_to_stable_repaired_misconception_does_not_block(
    service, sessions, item_id, usable_concept_id,
):
    _pass_delayed_recall(sessions, item_id)
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    _record_misconception(sessions, item_id)
    _repair_misconception(sessions, item_id)

    concept = service.promote_to_stable(usable_concept_id, reason="repaired + two cases")
    assert concept.workflow_status == "STABLE"


def test_promote_to_stable_requires_strong_application(
    service, sessions, item_id, usable_concept_id,
):
    _pass_delayed_recall(sessions, item_id)
    service.record_application(
        concept_id=usable_concept_id, evidence_level="PARTIAL", result="SUCCESS",
    )
    service.record_application(
        concept_id=usable_concept_id, evidence_level="PARTIAL", result="SUCCESS",
    )
    with pytest.raises(EvidenceGateError):
        service.promote_to_stable(usable_concept_id)


def test_promote_to_stable_succeeds_and_writes_status_event(
    service, sessions, conn, item_id, usable_concept_id,
):
    _pass_delayed_recall(sessions, item_id)
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )

    concept = service.promote_to_stable(
        usable_concept_id, reason="delayed recall + two cases + strong evidence",
    )
    assert concept.workflow_status == "STABLE"

    events = conn.execute(
        "SELECT from_status, to_status, reason FROM status_events "
        "WHERE entity_type='concept' AND entity_id=? ORDER BY id",
        (usable_concept_id,),
    ).fetchall()
    assert tuple(events[-1]) == (
        "USABLE", "STABLE", "delayed recall + two cases + strong evidence",
    )


def test_promote_to_stable_from_wrong_state_raises_invalid_transition(
    service, active_concept_id,
):
    # active_concept_id is ACTIVE, not USABLE.
    with pytest.raises(InvalidTransitionError):
        service.promote_to_stable(active_concept_id)


# ---------------------------------------------------------------------------
# retire(): STABLE -> RETIRED requires explicit reason (proxy for "用户确认")
# ---------------------------------------------------------------------------

@pytest.fixture()
def stable_concept_id(service, sessions, item_id, usable_concept_id) -> int:
    _pass_delayed_recall(sessions, item_id)
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    service.record_application(
        concept_id=usable_concept_id, evidence_level="STRONG", result="SUCCESS",
    )
    service.promote_to_stable(usable_concept_id, reason="stable now")
    return usable_concept_id


def test_retire_requires_explicit_reason(service, stable_concept_id):
    with pytest.raises(EvidenceGateError):
        service.retire(stable_concept_id, reason="")


def test_retire_requires_non_whitespace_reason(service, stable_concept_id):
    with pytest.raises(EvidenceGateError):
        service.retire(stable_concept_id, reason="   ")


def test_retire_succeeds_with_explicit_reason(service, conn, stable_concept_id):
    concept = service.retire(stable_concept_id, reason="confirmed no active recall need")
    assert concept.workflow_status == "RETIRED"

    events = conn.execute(
        "SELECT from_status, to_status, reason FROM status_events "
        "WHERE entity_type='concept' AND entity_id=? ORDER BY id",
        (stable_concept_id,),
    ).fetchall()
    assert tuple(events[-1]) == (
        "STABLE", "RETIRED", "confirmed no active recall need",
    )


def test_retire_from_wrong_state_raises_invalid_transition(service, usable_concept_id):
    # usable_concept_id is USABLE, not STABLE.
    with pytest.raises(InvalidTransitionError):
        service.retire(usable_concept_id, reason="not applicable yet")


# ---------------------------------------------------------------------------
# reactivate(): plain adjacency delegation, no extra evidence gate
# ---------------------------------------------------------------------------

@pytest.fixture()
def retired_concept_id(service, stable_concept_id) -> int:
    service.retire(stable_concept_id, reason="pausing review")
    return stable_concept_id


def test_reactivate_succeeds_with_no_evidence_required(service, conn, retired_concept_id):
    concept = service.reactivate(retired_concept_id, reason="new research need")
    assert concept.workflow_status == "REACTIVATED"

    events = conn.execute(
        "SELECT from_status, to_status, reason FROM status_events "
        "WHERE entity_type='concept' AND entity_id=? ORDER BY id",
        (retired_concept_id,),
    ).fetchall()
    assert tuple(events[-1]) == (
        "RETIRED", "REACTIVATED", "new research need",
    )


def test_reactivate_from_wrong_state_raises_invalid_transition(service, active_concept_id):
    with pytest.raises(InvalidTransitionError):
        service.reactivate(active_concept_id, reason="not applicable")
