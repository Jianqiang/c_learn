"""TDD for LearningOutputRepository (plan section 7.2 #learning_outputs,
section 12.1 `learn output list` / `learn output complete`).

Design under test:

- learning_outputs is seeded from syllabus-declared notebook/memo/map/ledger
  deliverables (plan: "从 syllabus 明确声明的 notebook/memo/map/ledger 等
  产出物导入"), one row per module.
- Status machine: PROPOSED -> ACTIVE -> SUBMITTED, any -> ARCHIVED, plus a
  direct PROPOSED -> SUBMITTED shortcut for the common case where a user
  just does the work and submits a reference without an explicit
  "I started this" step. SUBMITTED is terminal except for ARCHIVED.
- complete() is the *only* path that sets a reference and moves status to
  SUBMITTED. It requires a non-empty reference (plan 7.2: "用户完成并提交
  reference 后" -- there is no such thing as a reference-less completion).
- Nothing in the source/concept state machines is allowed to reach into
  learning_outputs. Plan 7.2 explicitly forbids "仅因 source 被 CONSUMED
  就自动完成 output" -- this is a structural invariant (no code path from
  SourceRepository touches the learning_outputs table at all), verified
  here by exercising a full source consumption flow and asserting the
  linked output's status is untouched.
"""
from __future__ import annotations

import sqlite3

import pytest

from learning_os.db import init_db
from learning_os.repositories import (
    InvalidTransitionError,
    LearningOutputRepository,
    ModuleRepository,
    SourceRepository,
)


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = init_db(tmp_path / "learning.db")
    yield c
    c.close()


@pytest.fixture()
def module_id(conn) -> int:
    return ModuleRepository(conn).create(slug="m1", name="Module 1", phase=1).id


@pytest.fixture()
def output_repo(conn) -> LearningOutputRepository:
    return LearningOutputRepository(conn)


# ---------------------------------------------------------------------------
# create / get / list_by_module
# ---------------------------------------------------------------------------

def test_create_output_defaults_to_proposed(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Capex memo")
    assert out.status == "PROPOSED"
    assert out.title == "Capex memo"
    assert out.reference is None
    fetched = output_repo.get(out.id)
    assert fetched == out


def test_create_output_accepts_optional_fields(output_repo, module_id):
    out = output_repo.create(
        module_id=module_id,
        title="Coverage map",
        kind="map",
        phase=2,
        required=True,
        source_file="投资技术学习清单.md",
        source_line=42,
        evidence_level="PARTIAL",
    )
    assert out.kind == "map"
    assert out.phase == 2
    assert out.required is True
    assert out.source_file == "投资技术学习清单.md"
    assert out.source_line == 42
    assert out.evidence_level == "PARTIAL"


def test_get_missing_output_raises_keyerror(output_repo):
    with pytest.raises(KeyError):
        output_repo.get(999)


def test_list_by_module_orders_by_id_and_filters_module(output_repo, conn, module_id):
    other_module_id = ModuleRepository(conn).create(
        slug="m2", name="Module 2", phase=1
    ).id
    a = output_repo.create(module_id=module_id, title="A")
    b = output_repo.create(module_id=module_id, title="B")
    output_repo.create(module_id=other_module_id, title="Other module output")

    listed = output_repo.list_by_module(module_id)
    assert [o.id for o in listed] == [a.id, b.id]


def test_list_by_module_empty_when_no_outputs(output_repo, module_id):
    assert output_repo.list_by_module(module_id) == []


# ---------------------------------------------------------------------------
# set_status
# ---------------------------------------------------------------------------

def test_set_status_proposed_to_active_writes_status_event(output_repo, conn, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    updated = output_repo.set_status(out.id, "ACTIVE", reason="started drafting")
    assert updated.status == "ACTIVE"

    events = conn.execute(
        "SELECT from_status, to_status, reason FROM status_events "
        "WHERE entity_type='learning_output' AND entity_id=? ORDER BY id",
        (out.id,),
    ).fetchall()
    assert [tuple(e) for e in events] == [("PROPOSED", "ACTIVE", "started drafting")]


def test_set_status_proposed_direct_to_submitted_allowed(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    updated = output_repo.set_status(out.id, "SUBMITTED")
    assert updated.status == "SUBMITTED"


def test_set_status_any_state_can_archive(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    output_repo.set_status(out.id, "ACTIVE")
    updated = output_repo.set_status(out.id, "ARCHIVED", reason="dropped")
    assert updated.status == "ARCHIVED"


def test_set_status_submitted_is_terminal_except_archive(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    output_repo.set_status(out.id, "SUBMITTED")
    with pytest.raises(InvalidTransitionError):
        output_repo.set_status(out.id, "ACTIVE")


def test_set_status_archived_is_terminal(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    output_repo.set_status(out.id, "ARCHIVED")
    with pytest.raises(InvalidTransitionError):
        output_repo.set_status(out.id, "ACTIVE")


def test_set_status_invalid_transition_does_not_mutate_row(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    output_repo.set_status(out.id, "SUBMITTED")
    with pytest.raises(InvalidTransitionError):
        output_repo.set_status(out.id, "PROPOSED")
    assert output_repo.get(out.id).status == "SUBMITTED"


# ---------------------------------------------------------------------------
# complete() -- the only path that writes `reference` and reaches SUBMITTED
# ---------------------------------------------------------------------------

def test_complete_sets_reference_and_status(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    completed = output_repo.complete(out.id, reference="https://example.com/memo")
    assert completed.status == "SUBMITTED"
    assert completed.reference == "https://example.com/memo"


def test_complete_from_active_also_allowed(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    output_repo.set_status(out.id, "ACTIVE")
    completed = output_repo.complete(out.id, reference="ref")
    assert completed.status == "SUBMITTED"


def test_complete_requires_non_empty_reference(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    with pytest.raises(ValueError):
        output_repo.complete(out.id, reference="")
    with pytest.raises(ValueError):
        output_repo.complete(out.id, reference="   ")
    with pytest.raises(ValueError):
        output_repo.complete(out.id, reference=None)  # type: ignore[arg-type]


def test_complete_already_submitted_output_rejected(output_repo, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    output_repo.complete(out.id, reference="first ref")
    with pytest.raises(InvalidTransitionError):
        output_repo.complete(out.id, reference="second ref")


def test_complete_writes_status_event(output_repo, conn, module_id):
    out = output_repo.create(module_id=module_id, title="Memo")
    output_repo.complete(out.id, reference="ref")
    events = conn.execute(
        "SELECT from_status, to_status FROM status_events "
        "WHERE entity_type='learning_output' AND entity_id=?",
        (out.id,),
    ).fetchall()
    assert [tuple(e) for e in events] == [("PROPOSED", "SUBMITTED")]


# ---------------------------------------------------------------------------
# structural invariant: source consumption never touches learning_outputs
# ---------------------------------------------------------------------------

def test_source_consumed_does_not_auto_complete_linked_output(
    output_repo, conn, module_id
):
    """Plan 7.2: "不能仅因 source 被 CONSUMED 就自动完成 output". There is no
    concept_id/source_id column on learning_outputs linking it to a specific
    source in v1 (only module_id), so the strongest test available is: fully
    drive a source through PROPOSED -> QUEUED -> OPEN -> CONSUMED in the same
    module as an output, and confirm the output row is completely untouched.
    """
    out = output_repo.create(module_id=module_id, title="Memo")

    source_repo = SourceRepository(conn)
    source = source_repo.create(
        module_id=module_id, title="Some reading", type="article",
        scope_confirmed=True,
    )
    source_repo.set_status(source.id, "QUEUED")
    source_repo.set_status(source.id, "OPEN")
    source_repo.set_status(source.id, "CONSUMED")

    unchanged = output_repo.get(out.id)
    assert unchanged.status == "PROPOSED"
    assert unchanged.reference is None
