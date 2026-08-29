"""TDD for the Next Best Actions recommender (plan section 11).

Plan 11 is a deterministic priority table, not a scoring formula:

    P1  explicit research dependency
    P2  current ACTIVE concept repair
    P3  important concept with recent failure/high-confidence error
    P4  approved QUEUED source (only current_phase and before, and
        review_load < 0.8)

Output is 2-4 actions, each carrying action_type/target/estimated_minutes/
reason/expected_output. The same target must never appear twice (dedup);
when a target would qualify under more than one tier, the highest-priority
(lowest-numbered) tier wins and supplies the reason.

See recommendation_service.py's module docstring for the exact mechanical
proxies this v1 implementation uses for "recent failure", "high-confidence
error", and "important" (plan 11 states the priority *names* but, like
plan 6.4's evidence gates, leaves the precise trigger to the implementation
as long as it is deterministic, explainable, and documented).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from learning_os.db import init_db
from learning_os.repositories import (
    ConceptRepository,
    FocusRepository,
    ModuleRepository,
    SourceRepository,
)
from learning_os.services.recommendation_service import (
    DEFAULT_CONCEPT_ACTION_MINUTES,
    DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    DEFAULT_SOURCE_ACTION_MINUTES,
    REVIEW_LOAD_GATE,
    RecommendationService,
)
from learning_os.services.session_service import SessionService

NOW = datetime(2026, 1, 1, 12, 0, 0)


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    return init_db(tmp_path / "learning.db")


@pytest.fixture()
def modules(conn) -> ModuleRepository:
    return ModuleRepository(conn)


@pytest.fixture()
def concepts(conn) -> ConceptRepository:
    return ConceptRepository(conn)


@pytest.fixture()
def sources(conn) -> SourceRepository:
    return SourceRepository(conn)


@pytest.fixture()
def focus(conn) -> FocusRepository:
    return FocusRepository(conn)


@pytest.fixture()
def sessions(conn) -> SessionService:
    return SessionService(conn)


@pytest.fixture()
def service(conn) -> RecommendationService:
    return RecommendationService(conn)


@pytest.fixture()
def module1(modules) -> int:
    return modules.create(slug="m1", name="Module 1", phase=1).id


def _make_concept(concepts, module_id, slug, name="C", importance=None, status=None) -> int:
    concept = concepts.create(module_id=module_id, slug=slug, name=name, importance=importance)
    if status is not None:
        # walk the adjacency chain far enough to reach `status`
        chain = ["QUEUED", "ACTIVE", "USABLE", "STABLE", "RETIRED", "REACTIVATED"]
        for step in chain[1 : chain.index(status) + 1]:
            concepts.set_status(concept.id, step, reason="test setup")
    return concept.id


def _make_item(conn, concept_id) -> int:
    cur = conn.execute(
        "INSERT INTO items (concept_id, type, prompt, grading_mode, reference_answer) "
        "VALUES (?, 'numeric', 'q', 'deterministic', '1')",
        (concept_id,),
    )
    conn.commit()
    return cur.lastrowid


def _record_attempt(sessions, item_id, *, outcome, confidence=None, target_id=1):
    session = sessions.start_or_resume(session_type="drill", target_type="concept", target_id=target_id)
    sessions.record_attempt(session.id, item_id, answer="x", outcome=outcome, confidence=confidence)


# ---------------------------------------------------------------------------
# Empty / baseline
# ---------------------------------------------------------------------------

def test_recommend_returns_empty_when_no_candidates(service):
    assert service.recommend(now=NOW) == []


# ---------------------------------------------------------------------------
# P1: explicit research dependency
# ---------------------------------------------------------------------------

def test_p1_dependency_concept_produces_drill_action(service, concepts, module1):
    concept_id = _make_concept(concepts, module1, "c1")
    actions = service.recommend(now=NOW, dependency_concept_ids=[concept_id])
    assert len(actions) == 1
    action = actions[0]
    assert action.priority == 1
    assert action.action_type == "drill"
    assert action.target_type == "concept"
    assert action.target_id == concept_id
    assert "dependency" in action.reason.lower()
    assert action.estimated_minutes == DEFAULT_CONCEPT_ACTION_MINUTES
    assert action.expected_output


def test_p1_dedups_duplicate_dependency_ids(service, concepts, module1):
    concept_id = _make_concept(concepts, module1, "c1")
    actions = service.recommend(
        now=NOW, dependency_concept_ids=[concept_id, concept_id],
    )
    assert len(actions) == 1


def test_p1_unknown_dependency_concept_raises_keyerror(service):
    with pytest.raises(KeyError):
        service.recommend(now=NOW, dependency_concept_ids=[99999])


# ---------------------------------------------------------------------------
# P2: current ACTIVE concept repair
# ---------------------------------------------------------------------------

def test_p2_active_concept_with_recent_failure_produces_repair_action(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", status="ACTIVE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="MISS")

    actions = service.recommend(now=NOW)
    assert len(actions) == 1
    assert actions[0].priority == 2
    assert actions[0].action_type == "repair"
    assert actions[0].target_id == concept_id


def test_p2_active_concept_without_failure_not_recommended(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", status="ACTIVE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="PASS")

    assert service.recommend(now=NOW) == []


def test_p2_active_concept_with_no_attempts_not_recommended(
    service, concepts, module1,
):
    _make_concept(concepts, module1, "c1", status="ACTIVE")
    assert service.recommend(now=NOW) == []


# ---------------------------------------------------------------------------
# P3: important concept with recent failure / high-confidence error
# ---------------------------------------------------------------------------

def test_p3_important_concept_with_recent_failure_produces_action(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", importance="high", status="USABLE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="MISS")

    actions = service.recommend(now=NOW)
    assert len(actions) == 1
    assert actions[0].priority == 3
    assert actions[0].target_id == concept_id
    assert "failure" in actions[0].reason.lower()


def test_p3_important_concept_with_high_confidence_error_produces_action(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", importance="high", status="USABLE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="PARTIAL", confidence=0.9)

    actions = service.recommend(now=NOW)
    assert len(actions) == 1
    assert actions[0].priority == 3
    assert "confidence" in actions[0].reason.lower()


def test_p3_low_confidence_partial_not_flagged_as_high_confidence_error(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", importance="high", status="USABLE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="PARTIAL", confidence=0.2)

    assert service.recommend(now=NOW) == []


def test_p3_unimportant_concept_not_recommended(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", importance=None, status="USABLE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="MISS")

    assert service.recommend(now=NOW) == []


def test_p3_retired_important_concept_not_recommended(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", importance="high", status="USABLE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="MISS")
    concepts.set_status(concept_id, "STABLE", reason="t")
    concepts.set_status(concept_id, "RETIRED", reason="t")

    assert service.recommend(now=NOW) == []


def test_dedup_prefers_higher_priority_when_same_target_qualifies_for_multiple_tiers(
    service, conn, concepts, sessions, module1,
):
    # ACTIVE + important + recent failure qualifies for both P2 and P3;
    # dedup must keep only the P2 (higher-priority) occurrence.
    concept_id = _make_concept(concepts, module1, "c1", importance="high", status="ACTIVE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="MISS")

    actions = service.recommend(now=NOW)
    assert len(actions) == 1
    assert actions[0].priority == 2
    assert actions[0].action_type == "repair"


# ---------------------------------------------------------------------------
# P4: approved QUEUED source
# ---------------------------------------------------------------------------

def _queue_source(sources, module_id, **kwargs) -> int:
    defaults = dict(
        module_id=module_id, title="S1", type="article",
        scope_confirmed=True,
    )
    defaults.update(kwargs)
    source = sources.create(**defaults)
    sources.set_status(source.id, "QUEUED", reason="approved")
    return source.id


def test_p4_queued_source_within_phase_and_low_review_load_recommended(
    service, sources, module1,
):
    source_id = _queue_source(sources, module1, estimated_minutes=15, output_hint="write a summary")
    actions = service.recommend(now=NOW)
    assert len(actions) == 1
    action = actions[0]
    assert action.priority == 4
    assert action.action_type == "learn"
    assert action.target_type == "source"
    assert action.target_id == source_id
    assert action.estimated_minutes == 15
    assert action.expected_output == "write a summary"


def test_p4_uses_default_minutes_and_generated_output_when_absent(
    service, sources, module1,
):
    source_id = _queue_source(sources, module1)
    actions = service.recommend(now=NOW)
    assert len(actions) == 1
    assert actions[0].estimated_minutes == DEFAULT_SOURCE_ACTION_MINUTES
    assert actions[0].expected_output


def test_p4_filtered_by_resource_mode(conn, service, module1):
    # A non-consumable source can never legitimately reach QUEUED through
    # SourceRepository.set_status() (plan 6.2's own gate), so this row is
    # inserted directly to prove the recommender's filter is defense-in-
    # depth against data written by another path (e.g. bulk seed import).
    conn.execute(
        "INSERT INTO sources (module_id, title, type, status, resource_mode, "
        "pace_mode, scope_confirmed) VALUES (?, 'S', 'article', 'QUEUED', "
        "'reference', 'self_paced', 1)",
        (module1,),
    )
    conn.commit()
    assert service.recommend(now=NOW) == []


def test_p4_filtered_by_pace_mode(conn, service, module1):
    conn.execute(
        "INSERT INTO sources (module_id, title, type, status, resource_mode, "
        "pace_mode, scope_confirmed) VALUES (?, 'S', 'article', 'QUEUED', "
        "'consumable', 'external_paced', 1)",
        (module1,),
    )
    conn.commit()
    assert service.recommend(now=NOW) == []


def test_p4_filtered_by_scope_confirmed(conn, service, module1):
    conn.execute(
        "INSERT INTO sources (module_id, title, type, status, resource_mode, "
        "pace_mode, scope_confirmed) VALUES (?, 'S', 'article', 'QUEUED', "
        "'consumable', 'self_paced', 0)",
        (module1,),
    )
    conn.commit()
    assert service.recommend(now=NOW) == []


def test_p4_filtered_by_phase_gate(service, sources, modules, focus):
    later_module = modules.create(slug="m2", name="Module 2", phase=3).id
    _queue_source(sources, later_module)
    focus.set_focus(current_phase=1)
    assert service.recommend(now=NOW) == []


def test_p4_included_when_phase_at_or_before_current_phase(service, sources, modules, focus):
    module_id = modules.create(slug="m2", name="Module 2", phase=2).id
    _queue_source(sources, module_id)
    focus.set_focus(current_phase=2)
    assert len(service.recommend(now=NOW)) == 1


def test_p4_no_focus_row_defaults_current_phase_to_one(service, sources, module1):
    # module1 is phase=1 and no focus_state row exists yet.
    _queue_source(sources, module1)
    assert len(service.recommend(now=NOW)) == 1


def test_p4_filtered_by_review_load_gate(conn, service, sources, module1, concepts, sessions):
    # Push review_load to >= REVIEW_LOAD_GATE by creating enough due items.
    concept_id = _make_concept(concepts, module1, "busy", status="ACTIVE")
    needed = int(REVIEW_LOAD_GATE * 1200 / 90) + 1
    for _ in range(needed):
        item_id = _make_item(conn, concept_id)
        conn.execute("INSERT INTO review_state (item_id) VALUES (?)", (item_id,))
    conn.commit()

    _queue_source(sources, module1)
    assert service.recommend(now=NOW) == []


# ---------------------------------------------------------------------------
# Cross-cutting: cap, shape
# ---------------------------------------------------------------------------

def test_recommend_caps_at_max_actions_default_four(service, sources, modules, focus):
    focus.set_focus(current_phase=1)
    for i in range(6):
        _queue_source(sources, modules.create(slug=f"m{i}", name=f"M{i}", phase=1).id)
    actions = service.recommend(now=NOW)
    assert len(actions) == 4


def test_recommend_respects_custom_max_actions(service, sources, modules, focus):
    focus.set_focus(current_phase=1)
    for i in range(6):
        _queue_source(sources, modules.create(slug=f"m{i}", name=f"M{i}", phase=1).id)
    actions = service.recommend(now=NOW, max_actions=2)
    assert len(actions) == 2


def test_every_action_has_reason_minutes_and_expected_output(
    service, concepts, module1,
):
    concept_id = _make_concept(concepts, module1, "c1")
    actions = service.recommend(now=NOW, dependency_concept_ids=[concept_id])
    for action in actions:
        assert action.reason
        assert action.estimated_minutes > 0
        assert action.expected_output


def test_high_confidence_threshold_is_overridable(
    service, conn, concepts, sessions, module1,
):
    concept_id = _make_concept(concepts, module1, "c1", importance="high", status="USABLE")
    item_id = _make_item(conn, concept_id)
    _record_attempt(sessions, item_id, outcome="PARTIAL", confidence=0.5)

    assert service.recommend(now=NOW) == []
    assert (
        service.recommend(now=NOW, high_confidence_threshold=0.4) != []
    )
