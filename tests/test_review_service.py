"""TDD tests for ReviewService (plan section 10): the SQLite-backed layer
around BaselineScheduler that persists review_state, enforces the v1
review budget, and implements Review selection ordering.

Design under test (learning_os.services.review_service.ReviewService):

- get_or_create(item_id): a brand-new item has no review_state row yet;
  the service creates one with due_at=None (immediately due) on first
  touch instead of requiring a separate "register" step.
- record_outcome(item_id, outcome, now): runs BaselineScheduler.next_due()
  and persists the result to the review_state table.
- confirm_repair(item_id, now): the only way to un-leech an item.
- due_items(now): active items whose due_at is NULL or <= now.
- review_load(now, per_item_seconds=...): 今日 due item 的预计秒数 / 1200
  (plan 10.2). No estimated-per-item-seconds column exists on items in
  v1, so this defaults to DEFAULT_ITEM_SECONDS (documented assumption,
  overridable per call).
- select_batch(...): Review selection (10.5) within MAX_REVIEW_ITEMS=12 /
  MAX_REVIEW_TIME=20min, ordered by:
    1. explicit dependency item_ids (research/application dependency)
    2. items belonging to the given active_concept_ids
    3. items belonging to important_concept_ids
    4. everything else due
  stopping (not erroring) once either budget is hit, and always
  attaching a human-readable `reason` per selected item -- plan 10.5
  requires every review item to show why it was picked.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from learning_os.db import init_db
from learning_os.repositories import ConceptRepository, ModuleRepository
from learning_os.services.review_service import (
    DEFAULT_ITEM_SECONDS,
    MAX_REVIEW_ITEMS,
    MAX_REVIEW_TIME_SECONDS,
    ReviewService,
)

NOW = datetime(2026, 1, 1, 12, 0, 0)


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    return init_db(tmp_path / "learning.db")


@pytest.fixture()
def make_item(conn):
    module = ModuleRepository(conn).create(slug="m1", name="Module 1", phase=1)

    def _make(concept_slug="c1", concept_name="Concept 1", importance=None):
        try:
            concept = ConceptRepository(conn).get_by_slug(concept_slug)
        except KeyError:
            concept = ConceptRepository(conn).create(
                module_id=module.id, slug=concept_slug, name=concept_name,
                importance=importance,
            )
        cur = conn.execute(
            "INSERT INTO items (concept_id, type, prompt, grading_mode, reference_answer) "
            "VALUES (?, 'numeric', 'q', 'deterministic', '1')",
            (concept.id,),
        )
        conn.commit()
        return cur.lastrowid, concept.id

    return _make


@pytest.fixture()
def service(conn) -> ReviewService:
    return ReviewService(conn)


# ---------------------------------------------------------------------------
# get_or_create / record_outcome persistence
# ---------------------------------------------------------------------------

def test_get_or_create_makes_a_row_due_immediately(service, make_item):
    item_id, _ = make_item()
    state = service.get_or_create(item_id)
    assert state.item_id == item_id
    assert state.due_at is None  # NULL due_at counts as due now
    assert state.active is True


def test_get_or_create_is_idempotent(service, make_item):
    item_id, _ = make_item()
    first = service.get_or_create(item_id)
    second = service.get_or_create(item_id)
    assert first.item_id == second.item_id


def test_record_outcome_persists_scheduler_result(service, make_item):
    item_id, _ = make_item()
    state = service.record_outcome(item_id, outcome="PASS", now=NOW)
    assert state.due_at == NOW + timedelta(days=1)
    reloaded = service.get_or_create(item_id)
    assert reloaded.due_at == NOW + timedelta(days=1)
    assert reloaded.last_outcome == "PASS"


def test_record_outcome_twice_advances_ladder_across_calls(service, make_item):
    item_id, _ = make_item()
    service.record_outcome(item_id, outcome="PASS", now=NOW)
    state = service.record_outcome(item_id, outcome="PASS", now=NOW)
    assert state.due_at == NOW + timedelta(days=3)


def test_record_outcome_leeches_after_three_failures(service, make_item):
    item_id, _ = make_item()
    service.record_outcome(item_id, outcome="MISS", now=NOW)
    service.record_outcome(item_id, outcome="MISS", now=NOW)
    state = service.record_outcome(item_id, outcome="MISS", now=NOW)
    assert state.intervention_required is True
    assert state.active is False


def test_confirm_repair_reactivates_leeched_item(service, make_item):
    item_id, _ = make_item()
    for _ in range(3):
        service.record_outcome(item_id, outcome="MISS", now=NOW)
    state = service.confirm_repair(item_id, now=NOW)
    assert state.active is True
    assert state.intervention_required is False


def test_confirm_repair_on_unknown_item_raises(service):
    with pytest.raises(KeyError):
        service.confirm_repair(999, now=NOW)


# ---------------------------------------------------------------------------
# due_items
# ---------------------------------------------------------------------------

def test_due_items_includes_never_scheduled_item(service, make_item):
    item_id, _ = make_item()
    service.get_or_create(item_id)
    due = service.due_items(now=NOW)
    assert item_id in [d.item_id for d in due]


def test_due_items_excludes_future_due_at(service, make_item):
    item_id, _ = make_item()
    service.record_outcome(item_id, outcome="PASS", now=NOW)  # due in 1d
    due = service.due_items(now=NOW)
    assert item_id not in [d.item_id for d in due]


def test_due_items_includes_past_due_at(service, make_item):
    item_id, _ = make_item()
    service.record_outcome(item_id, outcome="PASS", now=NOW)
    due = service.due_items(now=NOW + timedelta(days=2))
    assert item_id in [d.item_id for d in due]


def test_due_items_excludes_suspended_leech_items(service, make_item):
    item_id, _ = make_item()
    for _ in range(3):
        service.record_outcome(item_id, outcome="MISS", now=NOW)
    due = service.due_items(now=NOW)
    assert item_id not in [d.item_id for d in due]


# ---------------------------------------------------------------------------
# review_load (10.2)
# ---------------------------------------------------------------------------

def test_review_load_zero_when_nothing_due(service):
    assert service.review_load(now=NOW) == 0.0


def test_review_load_uses_default_item_seconds(service, make_item):
    item_id, _ = make_item()
    service.get_or_create(item_id)
    load = service.review_load(now=NOW)
    assert load == pytest.approx(DEFAULT_ITEM_SECONDS / 1200)


def test_review_load_scales_with_due_item_count(service, make_item):
    id1, _ = make_item(concept_slug="c1")
    id2, _ = make_item(concept_slug="c2", concept_name="Concept 2")
    service.get_or_create(id1)
    service.get_or_create(id2)
    load = service.review_load(now=NOW)
    assert load == pytest.approx(2 * DEFAULT_ITEM_SECONDS / 1200)


def test_review_load_respects_custom_per_item_seconds(service, make_item):
    item_id, _ = make_item()
    service.get_or_create(item_id)
    load = service.review_load(now=NOW, per_item_seconds=600)
    assert load == pytest.approx(600 / 1200)


# ---------------------------------------------------------------------------
# select_batch (10.5) + budgets (10.1)
# ---------------------------------------------------------------------------

def test_select_batch_prioritizes_explicit_dependency_first(service, make_item):
    dep_id, _ = make_item(concept_slug="c1")
    other_id, _ = make_item(concept_slug="c2", concept_name="Concept 2")
    service.get_or_create(dep_id)
    service.get_or_create(other_id)
    result = service.select_batch(now=NOW, dependency_item_ids={dep_id})
    assert result[0].item_id == dep_id
    assert "dependency" in result[0].reason.lower()


def test_select_batch_prioritizes_active_concept_over_generic_due(service, make_item):
    active_id, active_concept_id = make_item(concept_slug="c1")
    other_id, _ = make_item(concept_slug="c2", concept_name="Concept 2")
    service.get_or_create(active_id)
    service.get_or_create(other_id)
    result = service.select_batch(now=NOW, active_concept_ids={active_concept_id})
    assert result[0].item_id == active_id


def test_select_batch_prioritizes_important_concept_over_generic_due(service, make_item):
    important_id, important_concept_id = make_item(concept_slug="c1")
    other_id, _ = make_item(concept_slug="c2", concept_name="Concept 2")
    service.get_or_create(important_id)
    service.get_or_create(other_id)
    result = service.select_batch(
        now=NOW, important_concept_ids={important_concept_id},
    )
    assert result[0].item_id == important_id


def test_select_batch_every_item_has_a_reason(service, make_item):
    item_id, _ = make_item()
    service.get_or_create(item_id)
    result = service.select_batch(now=NOW)
    assert all(r.reason for r in result)
    assert all(r.budget_exception is False for r in result)


def test_select_batch_stops_at_max_review_items(service, make_item):
    for i in range(MAX_REVIEW_ITEMS + 3):
        item_id, _ = make_item(concept_slug=f"c{i}", concept_name=f"Concept {i}")
        service.get_or_create(item_id)
    result = service.select_batch(now=NOW)
    assert len(result) == MAX_REVIEW_ITEMS


def test_select_batch_stops_at_max_review_time(service, make_item):
    """A batch must never let the *next* item push elapsed time over the
    20-minute budget. With per_item=401s (MAX_REVIEW_TIME_SECONDS//3+1),
    2 items fit at 802s but a 3rd would reach 1203s > 1200s budget, so
    the batch must stop at 2, not 3.
    """
    per_item = MAX_REVIEW_TIME_SECONDS // 3 + 1
    for i in range(6):
        item_id, _ = make_item(concept_slug=f"c{i}", concept_name=f"Concept {i}")
        service.get_or_create(item_id)
    result = service.select_batch(now=NOW, per_item_seconds=per_item)
    assert len(result) == 2


def test_select_batch_never_exceeds_time_budget_when_it_fits_exactly(service, make_item):
    """Boundary case: per_item * n == max_time_seconds exactly must still
    include the n-th item (no off-by-one on the inclusive boundary)."""
    per_item = MAX_REVIEW_TIME_SECONDS // 4  # 4 items exactly fill the budget
    for i in range(6):
        item_id, _ = make_item(concept_slug=f"c{i}", concept_name=f"Concept {i}")
        service.get_or_create(item_id)
    result = service.select_batch(now=NOW, per_item_seconds=per_item)
    assert len(result) == 4


def test_select_batch_single_oversized_item_is_still_selected_alone(service, make_item):
    """If a single due item's own cost already exceeds the whole time
    budget, it should still be surfaced alone (with its real reason)
    instead of returning an empty batch and deadlocking review forever.
    No second item may be added after it since the budget is exhausted.

    Architect review (2026-08-29): this bypasses the plan's stated "hard"
    20-minute budget, so the returned item must be flagged
    budget_exception=True and its reason must say so explicitly -- a
    caller (CLI/UI) can then present it as an explicit exception instead
    of a normal review pick, rather than silently pretending the batch
    still fits inside 20 minutes.
    """
    item_id, _ = make_item(concept_slug="c1")
    other_id, _ = make_item(concept_slug="c2", concept_name="Concept 2")
    service.get_or_create(item_id)
    service.get_or_create(other_id)
    oversized_seconds = MAX_REVIEW_TIME_SECONDS + 1
    result = service.select_batch(now=NOW, per_item_seconds=oversized_seconds)
    assert len(result) == 1
    assert result[0].budget_exception is True
    assert "exceeds" in result[0].reason.lower()


def test_select_batch_normal_items_are_not_flagged_as_budget_exception(service, make_item):
    item_id, _ = make_item()
    service.get_or_create(item_id)
    result = service.select_batch(now=NOW, per_item_seconds=90)
    assert len(result) == 1
    assert result[0].budget_exception is False


def test_select_batch_excludes_leeched_items(service, make_item):
    leeched_id, _ = make_item(concept_slug="c1")
    for _ in range(3):
        service.record_outcome(leeched_id, outcome="MISS", now=NOW)
    result = service.select_batch(now=NOW)
    assert leeched_id not in [r.item_id for r in result]
