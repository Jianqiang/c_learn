"""Review & scheduling service (plan section 10): the persistence + budget
+ selection layer wrapped around the pure BaselineScheduler.

Responsibilities:
- get_or_create / record_outcome / confirm_repair: persist review_state
  rows, delegating the actual scheduling math to BaselineScheduler.
- due_items(): active items whose due_at is NULL or <= now.
- review_load(): 今日 due item 的预计秒数 / 1200 (plan 10.2). v1's items
  table has no per-item estimated-seconds column, so DEFAULT_ITEM_SECONDS
  is a documented placeholder assumption (90s/item, i.e. a quick drill
  question) that callers can override via per_item_seconds until content
  authoring adds a real estimate field.
- select_batch(): Review selection ordering (10.5) within the v1 budget
  (10.1): MAX_REVIEW_ITEMS=12, MAX_REVIEW_TIME=20min, first-to-trigger
  stops the batch. Every selected item carries a human-readable `reason`
  string per the plan's "避免产生不可解释的算法命令" requirement.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from learning_os.schedulers.baseline import BaselineScheduler, ReviewState

MAX_REVIEW_ITEMS = 12
MAX_REVIEW_TIME_SECONDS = 20 * 60
# Documented v1 placeholder: items has no estimated-seconds column yet, so
# review_load and batch-time-budget math assume a flat per-item cost until
# content authoring adds a real estimate. Overridable per call.
DEFAULT_ITEM_SECONDS = 90

_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _fmt(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime(_DATE_FMT) if dt is not None else None


def _parse(s: Optional[str]) -> Optional[datetime]:
    return datetime.strptime(s, _DATE_FMT) if s else None


@dataclass
class SelectedItem:
    item_id: int
    reason: str


class ReviewService:
    def __init__(self, conn: sqlite3.Connection, scheduler: Optional[BaselineScheduler] = None):
        self._conn = conn
        self._scheduler = scheduler or BaselineScheduler()

    # -- persistence -----------------------------------------------------

    def get_or_create(self, item_id: int) -> ReviewState:
        row = self._conn.execute(
            "SELECT item_id, due_at, stability, difficulty, last_outcome, "
            "last_reviewed_at, active, lapse_count, failure_streak, "
            "intervention_required, suspended_until, ladder_rung, "
            "outcome_history FROM review_state WHERE item_id=?",
            (item_id,),
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO review_state (item_id) VALUES (?)", (item_id,)
            )
            self._conn.commit()
            return self.get_or_create(item_id)
        return self._row_to_state(row)

    def record_outcome(self, item_id: int, *, outcome: str, now: datetime) -> ReviewState:
        state = self.get_or_create(item_id)
        new_state = self._scheduler.next_due(state, outcome=outcome, now=now)
        self._persist(new_state)
        return new_state

    def confirm_repair(self, item_id: int, *, now: datetime) -> ReviewState:
        row = self._conn.execute(
            "SELECT item_id FROM review_state WHERE item_id=?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"review_state for item {item_id} not found")
        state = self.get_or_create(item_id)
        repaired = self._scheduler.confirm_repair(state, now=now)
        self._persist(repaired)
        return repaired

    def _persist(self, state: ReviewState) -> None:
        self._conn.execute(
            "UPDATE review_state SET due_at=?, stability=?, difficulty=?, "
            "last_outcome=?, last_reviewed_at=?, active=?, lapse_count=?, "
            "failure_streak=?, intervention_required=?, suspended_until=?, "
            "ladder_rung=?, outcome_history=? WHERE item_id=?",
            (
                _fmt(state.due_at), state.stability, state.difficulty,
                state.last_outcome, _fmt(state.last_reviewed_at),
                int(state.active), state.lapse_count, state.failure_streak,
                int(state.intervention_required), _fmt(state.suspended_until),
                state.ladder_rung, json.dumps(list(state.outcome_history)),
                state.item_id,
            ),
        )
        self._conn.commit()

    def _row_to_state(self, row) -> ReviewState:
        return ReviewState(
            item_id=row[0],
            due_at=_parse(row[1]),
            stability=row[2],
            difficulty=row[3],
            last_outcome=row[4],
            last_reviewed_at=_parse(row[5]),
            active=bool(row[6]),
            lapse_count=row[7],
            failure_streak=row[8],
            intervention_required=bool(row[9]),
            suspended_until=_parse(row[10]),
            ladder_rung=row[11],
            outcome_history=tuple(json.loads(row[12])) if row[12] else (),
        )

    # -- queries -----------------------------------------------------------

    def due_items(self, *, now: datetime) -> list[ReviewState]:
        rows = self._conn.execute(
            "SELECT item_id, due_at, stability, difficulty, last_outcome, "
            "last_reviewed_at, active, lapse_count, failure_streak, "
            "intervention_required, suspended_until, ladder_rung, "
            "outcome_history FROM review_state "
            "WHERE active=1 AND (due_at IS NULL OR due_at <= ?) "
            "ORDER BY item_id ASC",
            (_fmt(now),),
        ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def review_load(self, *, now: datetime, per_item_seconds: int = DEFAULT_ITEM_SECONDS) -> float:
        due = self.due_items(now=now)
        return (len(due) * per_item_seconds) / 1200

    # -- selection (10.5) ----------------------------------------------------

    def _item_concept_id(self, item_id: int) -> Optional[int]:
        row = self._conn.execute(
            "SELECT concept_id FROM items WHERE id=?", (item_id,)
        ).fetchone()
        return row[0] if row else None

    def select_batch(
        self,
        *,
        now: datetime,
        dependency_item_ids: Iterable[int] = (),
        active_concept_ids: Iterable[int] = (),
        important_concept_ids: Iterable[int] = (),
        max_items: int = MAX_REVIEW_ITEMS,
        max_time_seconds: int = MAX_REVIEW_TIME_SECONDS,
        per_item_seconds: int = DEFAULT_ITEM_SECONDS,
    ) -> list[SelectedItem]:
        dependency_item_ids = set(dependency_item_ids)
        active_concept_ids = set(active_concept_ids)
        important_concept_ids = set(important_concept_ids)

        due = self.due_items(now=now)

        def priority_and_reason(state: ReviewState) -> tuple:
            if state.item_id in dependency_item_ids:
                return (1, "explicit research/application dependency")
            concept_id = self._item_concept_id(state.item_id)
            if concept_id in active_concept_ids:
                return (2, "belongs to current ACTIVE concept")
            if concept_id in important_concept_ids:
                return (3, "important concept, due for review")
            return (4, "due for review")

        ranked = sorted(
            due,
            key=lambda s: (priority_and_reason(s)[0], s.item_id),
        )

        selected: list[SelectedItem] = []
        elapsed_seconds = 0
        for state in ranked:
            if len(selected) >= max_items:
                break
            # Check the budget *before* committing to an item: adding this
            # item must not push elapsed_seconds past max_time_seconds.
            # The one exception is an empty batch -- if even a single due
            # item's own cost exceeds the whole budget, we still surface
            # that one item (it carries its real reason) rather than
            # silently returning an empty batch and deadlocking review
            # forever; no further item is added after it, since the
            # budget is already exhausted.
            if elapsed_seconds + per_item_seconds > max_time_seconds and selected:
                break
            _, reason = priority_and_reason(state)
            selected.append(SelectedItem(item_id=state.item_id, reason=reason))
            elapsed_seconds += per_item_seconds
            if elapsed_seconds >= max_time_seconds:
                break
        return selected
