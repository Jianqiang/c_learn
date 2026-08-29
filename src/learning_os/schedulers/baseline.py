"""V1 baseline scheduler (plan section 10.3/10.4): a pure, explainable
fixed-interval scheduler with leech detection. No FSRS, no ML ranking.

Ladder (days after first exposure, on consecutive PASS):
    1 -> 3 -> 7 -> 14 -> 30 (caps at 30)

On PARTIAL or MISS: immediate repair, next due in 1 day, ladder position
resets to the bottom (rung 0) so the next PASS goes to 1d again, not to
wherever the ladder previously was.

On MISCONCEPTION: same as PARTIAL/MISS (repair + restart from 1d) but is
tracked as a "true failure" outcome for leech purposes.

Leech condition (any one triggers intervention_required + active=False,
pausing auto-due):
    - 3 consecutive outcomes in {MISS, MISCONCEPTION} ("failure_streak").
      PARTIAL is a repair-triggering outcome but is NOT a "true failure"
      for this streak: it breaks/resets failure_streak back to 0 rather
      than extending it, so e.g. MISS, PARTIAL, MISS never trips the
      3-in-a-row rule on its own. This matches plan section 10.4, which
      defines the streak explicitly over {MISS, MISCONCEPTION}.
    - OR 4-of-the-last-5 outcomes are non-PASS (SKIPPED does not count
      as an outcome for this window; see below). PARTIAL still counts as
      non-PASS in this rolling window even though it doesn't extend
      failure_streak.

Once a ReviewState is leeched (active=False), next_due() refuses to
schedule further outcomes -- the plan requires an explicit human choice
(rewrite item / split concept / manual / retire) before resuming the
1d ladder. confirm_repair() is the only way back onto the ladder.

SKIPPED is a no-op for the ladder, failure streak, and leech window: it
means the user didn't attempt the item this session, not that they got
it wrong. It doesn't overwrite last_outcome so the ladder/leech judgment
is always based on the last *real* attempt outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Optional, Tuple

LADDER_DAYS: Tuple[int, ...] = (1, 3, 7, 14, 30)
FAILURE_OUTCOMES = {"MISS", "MISCONCEPTION"}
REAL_OUTCOMES = {"PASS", "PARTIAL", "MISS", "MISCONCEPTION"}
VALID_OUTCOMES = REAL_OUTCOMES | {"SKIPPED"}

LEECH_STREAK_THRESHOLD = 3
LEECH_WINDOW = 5
LEECH_WINDOW_NON_PASS_THRESHOLD = 4


@dataclass
class ReviewState:
    item_id: int
    due_at: Optional[datetime]
    stability: Optional[float]
    difficulty: Optional[float]
    last_outcome: Optional[str]
    last_reviewed_at: Optional[datetime]
    active: bool
    lapse_count: int
    failure_streak: int
    intervention_required: bool
    suspended_until: Optional[datetime]
    # Internal bookkeeping the DB layer doesn't need to expose as a column;
    # a persistence adapter can serialize this as JSON or keep only the
    # trailing window (any list-like of the last REAL_OUTCOMES entries).
    outcome_history: Tuple[str, ...] = ()
    # Ladder position is derived, not stored directly: rung 0 means "not on
    # the ladder yet / just reset", rung i means due_at was scheduled from
    # LADDER_DAYS[i - 1] on the most recent PASS.
    ladder_rung: int = 0


class BaselineScheduler:
    """Stateless: all state lives in the ReviewState passed in/out."""

    def next_due(
        self, state: ReviewState, *, outcome: str, now: datetime
    ) -> ReviewState:
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"invalid outcome: {outcome!r}")
        if not state.active:
            raise ValueError(
                f"item {state.item_id} is suspended (intervention_required); "
                "call confirm_repair() before scheduling further outcomes"
            )

        if outcome == "SKIPPED":
            # No-op: don't touch due_at, streaks, history, or last_outcome.
            return replace(state)

        if outcome == "PASS":
            next_rung = min(state.ladder_rung + 1, len(LADDER_DAYS))
            due_at = now + timedelta(days=LADDER_DAYS[next_rung - 1])
            new_failure_streak = 0
            new_lapse_count = state.lapse_count
            new_ladder_rung = next_rung
        else:  # PARTIAL, MISS, MISCONCEPTION: immediate repair, reset ladder
            due_at = now + timedelta(days=LADDER_DAYS[0])
            # failure_streak is the plan 10.4 "3 consecutive MISS/
            # MISCONCEPTION" counter. PARTIAL triggers a repair like a
            # failure, but is not itself a "true failure" for streak
            # purposes, so it breaks the streak back to 0 instead of
            # extending it (a MISS, PARTIAL, MISS sequence should not
            # read as "3 consecutive failures").
            if outcome in FAILURE_OUTCOMES:
                new_failure_streak = state.failure_streak + 1
            else:
                new_failure_streak = 0
            new_lapse_count = state.lapse_count + 1
            new_ladder_rung = 0

        new_history = (state.outcome_history + (outcome,))[-LEECH_WINDOW:]
        is_leech = self._is_leech(new_history, new_failure_streak)

        return replace(
            state,
            due_at=due_at,
            last_outcome=outcome,
            last_reviewed_at=now,
            failure_streak=new_failure_streak,
            lapse_count=new_lapse_count,
            outcome_history=new_history,
            ladder_rung=new_ladder_rung,
            intervention_required=is_leech,
            active=not is_leech,
        )

    def confirm_repair(self, state: ReviewState, *, now: datetime) -> ReviewState:
        """The only way to bring a leeched item back onto the schedule.

        Restarts the ladder from rung 0 (so the next PASS goes to 1d) and
        clears the failure streak, but deliberately keeps outcome_history
        and lapse_count as a historical record -- repair is not amnesty,
        it's an explicit human decision to try again.
        """
        if state.active or not state.intervention_required:
            raise ValueError(
                f"item {state.item_id} is not currently leeched; "
                "confirm_repair() only applies to intervention_required items"
            )
        return replace(
            state,
            active=True,
            intervention_required=False,
            failure_streak=0,
            ladder_rung=0,
            suspended_until=None,
        )

    @staticmethod
    def _is_leech(history: Tuple[str, ...], failure_streak: int) -> bool:
        if failure_streak >= LEECH_STREAK_THRESHOLD:
            return True
        window = history[-LEECH_WINDOW:]
        if len(window) == LEECH_WINDOW:
            non_pass = sum(1 for o in window if o != "PASS")
            if non_pass >= LEECH_WINDOW_NON_PASS_THRESHOLD:
                return True
        return False
