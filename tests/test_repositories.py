"""TDD for the model/repository layer: modules, sources, concepts and their
state machines (plan section 6), plus concept_sources, focus_state and
status_events bookkeeping.

State machines under test (from the plan):

Module:      AVAILABLE -> ACTIVE -> PAUSED (PAUSED <-> ACTIVE), any -> ARCHIVED
Source:      PROPOSED -> QUEUED -> OPEN -> CONSUMED
                                       -> SKIPPED
             PROPOSED -> VISIBLE, any -> ARCHIVED
Concept:     QUEUED -> ACTIVE -> USABLE -> STABLE -> RETIRED -> REACTIVATED -> ACTIVE

Every successful transition must also write a status_events row so changes
are explainable, and invalid transitions must be rejected (raise ValueError)
without mutating state.
"""
import pytest

from learning_os.db import init_db
from learning_os.repositories import (
    ConceptRepository,
    InvalidTransitionError,
    ModuleRepository,
    SourceRepository,
)


@pytest.fixture()
def conn(tmp_path):
    c = init_db(tmp_path / "learning.db")
    yield c
    c.close()


@pytest.fixture()
def module_repo(conn):
    return ModuleRepository(conn)


@pytest.fixture()
def source_repo(conn):
    return SourceRepository(conn)


@pytest.fixture()
def concept_repo(conn):
    return ConceptRepository(conn)


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

def test_create_module_defaults_to_available(module_repo):
    m = module_repo.create(slug="llm-econ", name="LLM Economics", phase=1)
    assert m.status == "AVAILABLE"
    fetched = module_repo.get_by_slug("llm-econ")
    assert fetched.id == m.id
    assert fetched.name == "LLM Economics"


def test_module_valid_transition_chain_writes_status_events(module_repo, conn):
    m = module_repo.create(slug="llm-econ", name="LLM Economics", phase=1)
    module_repo.set_status(m.id, "ACTIVE", reason="starting focus")
    module_repo.set_status(m.id, "PAUSED", reason="switching priorities")
    module_repo.set_status(m.id, "ACTIVE", reason="resuming")

    updated = module_repo.get_by_slug("llm-econ")
    assert updated.status == "ACTIVE"

    events = conn.execute(
        "SELECT from_status, to_status, reason FROM status_events "
        "WHERE entity_type='module' AND entity_id=? ORDER BY id",
        (m.id,),
    ).fetchall()
    assert [tuple(e) for e in events] == [
        ("AVAILABLE", "ACTIVE", "starting focus"),
        ("ACTIVE", "PAUSED", "switching priorities"),
        ("PAUSED", "ACTIVE", "resuming"),
    ]


def test_module_any_state_can_archive(module_repo):
    m = module_repo.create(slug="m2", name="M2", phase=1)
    module_repo.set_status(m.id, "ARCHIVED", reason="dropped")
    assert module_repo.get_by_slug("m2").status == "ARCHIVED"


def test_module_invalid_transition_rejected(module_repo):
    m = module_repo.create(slug="m3", name="M3", phase=1)
    with pytest.raises(InvalidTransitionError):
        module_repo.set_status(m.id, "PAUSED", reason="skip active")
    # state must be unchanged after a rejected transition
    assert module_repo.get_by_slug("m3").status == "AVAILABLE"


def test_module_archived_is_terminal(module_repo):
    m = module_repo.create(slug="m4", name="M4", phase=1)
    module_repo.set_status(m.id, "ARCHIVED", reason="done")
    with pytest.raises(InvalidTransitionError):
        module_repo.set_status(m.id, "ACTIVE", reason="revive")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def test_create_source_requires_existing_module(module_repo, source_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    s = source_repo.create(
        module_id=m.id,
        title="Kaplan Scaling Laws",
        type="paper",
        resource_mode="consumable",
        pace_mode="self_paced",
    )
    assert s.status == "PROPOSED"
    assert s.resource_mode == "consumable"


def test_source_consumable_happy_path(module_repo, source_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    s = source_repo.create(
        module_id=m.id, title="Paper", type="paper",
        resource_mode="consumable", pace_mode="self_paced",
    )
    source_repo.set_status(s.id, "QUEUED", reason="approved")
    source_repo.set_status(s.id, "OPEN", reason="started reading")
    source_repo.set_status(s.id, "CONSUMED", reason="finished")
    assert source_repo.get(s.id).status == "CONSUMED"


def test_source_open_can_be_skipped(module_repo, source_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    s = source_repo.create(
        module_id=m.id, title="Paper", type="paper",
        resource_mode="consumable", pace_mode="self_paced",
    )
    source_repo.set_status(s.id, "QUEUED")
    source_repo.set_status(s.id, "OPEN")
    source_repo.set_status(s.id, "SKIPPED", reason="not relevant anymore")
    assert source_repo.get(s.id).status == "SKIPPED"


def test_reference_source_goes_proposed_to_visible(module_repo, source_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    s = source_repo.create(
        module_id=m.id, title="Reference doc", type="doc",
        resource_mode="reference", pace_mode="self_paced",
    )
    source_repo.set_status(s.id, "VISIBLE", reason="confirmed for navigation")
    assert source_repo.get(s.id).status == "VISIBLE"


def test_source_queued_cannot_skip_directly(module_repo, source_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    s = source_repo.create(
        module_id=m.id, title="Paper", type="paper",
        resource_mode="consumable", pace_mode="self_paced",
    )
    source_repo.set_status(s.id, "QUEUED")
    with pytest.raises(InvalidTransitionError):
        source_repo.set_status(s.id, "SKIPPED")


def test_source_any_status_can_archive(module_repo, source_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    s = source_repo.create(
        module_id=m.id, title="Paper", type="paper",
        resource_mode="consumable", pace_mode="self_paced",
    )
    source_repo.set_status(s.id, "ARCHIVED", reason="duplicate")
    assert source_repo.get(s.id).status == "ARCHIVED"


# ---------------------------------------------------------------------------
# Concepts
# ---------------------------------------------------------------------------

def test_concept_full_lifecycle(module_repo, concept_repo, conn):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    c = concept_repo.create(module_id=m.id, slug="kv-cache", name="KV cache")
    assert c.workflow_status == "QUEUED"

    concept_repo.set_status(c.id, "ACTIVE", reason="starting")
    concept_repo.set_status(c.id, "USABLE", reason="passed rubric atom + partial evidence")
    concept_repo.set_status(c.id, "STABLE", reason="two applications + delayed recall")
    concept_repo.set_status(c.id, "RETIRED", reason="stable enough")
    concept_repo.set_status(c.id, "REACTIVATED", reason="new research need")
    concept_repo.set_status(c.id, "ACTIVE", reason="resuming work")

    assert concept_repo.get(c.id).workflow_status == "ACTIVE"

    to_statuses = [
        row[0]
        for row in conn.execute(
            "SELECT to_status FROM status_events WHERE entity_type='concept' "
            "AND entity_id=? ORDER BY id",
            (c.id,),
        ).fetchall()
    ]
    assert to_statuses == [
        "ACTIVE", "USABLE", "STABLE", "RETIRED", "REACTIVATED", "ACTIVE",
    ]


def test_concept_cannot_skip_active(module_repo, concept_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    c = concept_repo.create(module_id=m.id, slug="c1", name="C1")
    with pytest.raises(InvalidTransitionError):
        concept_repo.set_status(c.id, "USABLE")


def test_concept_status_change_is_explicit_no_silent_default(module_repo, concept_repo):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    c = concept_repo.create(module_id=m.id, slug="c1", name="C1")
    # Creating never silently marks ACTIVE/USABLE; must stay QUEUED until
    # a user/system explicitly calls set_status.
    assert concept_repo.get(c.id).workflow_status == "QUEUED"


# ---------------------------------------------------------------------------
# concept_sources link + focus_state single-row invariant
# ---------------------------------------------------------------------------

def test_concept_source_link(module_repo, concept_repo, source_repo, conn):
    m = module_repo.create(slug="m1", name="M1", phase=1)
    c = concept_repo.create(module_id=m.id, slug="c1", name="C1")
    s = source_repo.create(
        module_id=m.id, title="Paper", type="paper",
        resource_mode="consumable", pace_mode="self_paced",
    )
    concept_repo.link_source(c.id, s.id, relationship="introduces")
    rows = conn.execute(
        "SELECT concept_id, source_id, relationship FROM concept_sources"
    ).fetchall()
    assert tuple(rows[0]) == (c.id, s.id, "introduces")


def test_focus_state_only_one_active_row(conn, module_repo):
    from learning_os.repositories import FocusRepository

    m = module_repo.create(slug="m1", name="M1", phase=1)
    focus_repo = FocusRepository(conn)
    focus_repo.set_focus(current_phase=1, target_type="module", target_id=m.id, rationale="kickoff")
    focus_repo.set_focus(current_phase=1, target_type="module", target_id=m.id, rationale="still here")

    rows = conn.execute("SELECT COUNT(*) FROM focus_state").fetchall()
    assert rows[0][0] == 1

    current = focus_repo.get_current()
    assert current.rationale == "still here"

    events = conn.execute(
        "SELECT entity_type FROM status_events WHERE entity_type='focus_state'"
    ).fetchall()
    assert len(events) == 2
