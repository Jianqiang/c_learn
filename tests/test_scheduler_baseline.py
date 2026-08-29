"""TDD tests for the v1 baseline scheduler (plan section 10.3/10.4).

Scheduler.next_due(review_state, outcome, now) is a pure function: given the
current review_state row (as a dict/mapping with at least
`failure_streak`, `lapse_count`, `last_outcome`, `outcome_history`) plus the
outcome just recorded and the current time, it returns a dict of column
updates to apply to review_state (due_at, last_outcome, last_reviewed_at,
lapse_count, failure_streak, intervention_required, active/suspended_until).

Baseline rule set under test:

    PASS after first exposure: 1d -> 3d -> 7d -> 14d -> 30d
    PARTIAL/MISS:            immediate repair, next due in 1d
    MISCONCEPTION:            repair, restart the ladder from 1d

Leech (plan section 10.4): 3 consecutive MISS/MISCONCEPTION, OR 4-of-last-5
non-PASS -> intervention_required=True, active=False (auto-due paused).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from learning_os.schedulers.baseline import BaselineScheduler, ReviewState

NOW = datetime(2026, 1, 1, 12, 0, 0)


def fresh_state() -> ReviewState:
    return ReviewState(
        item_id=1,
        due_at=None,
        stability=None,
        difficulty=None,
        last_outcome=None,
        last_reviewed_at=None,
        active=True,
        lapse_count=0,
        failure_streak=0,
        intervention_required=False,
        suspended_until=None,
        outcome_history=(),
    )


# ---------------------------------------------------------------------------
# PASS ladder
# ---------------------------------------------------------------------------

def test_first_pass_schedules_one_day_out():
    scheduler = BaselineScheduler()
    result = scheduler.next_due(fresh_state(), outcome="PASS", now=NOW)
    assert result.due_at == NOW + timedelta(days=1)
    assert result.failure_streak == 0
    assert result.last_outcome == "PASS"


def test_second_consecutive_pass_advances_to_three_days():
    scheduler = BaselineScheduler()
    state = fresh_state()
    state = scheduler.next_due(state, outcome="PASS", now=NOW)  # rung 1: 1d
    result = scheduler.next_due(state, outcome="PASS", now=NOW)  # rung 2: 3d
    assert result.due_at == NOW + timedelta(days=3)


def test_pass_ladder_full_progression():
    scheduler = BaselineScheduler()
    state = fresh_state()
    expected_days = [1, 3, 7, 14, 30]
    for expected in expected_days:
        state = scheduler.next_due(state, outcome="PASS", now=NOW)
        assert state.due_at == NOW + timedelta(days=expected)


def test_pass_ladder_stays_at_thirty_days_once_maxed():
    scheduler = BaselineScheduler()
    state = fresh_state()
    for _ in range(5):
        state = scheduler.next_due(state, outcome="PASS", now=NOW)
    assert state.due_at == NOW + timedelta(days=30)
    state = scheduler.next_due(state, outcome="PASS", now=NOW)
    assert state.due_at == NOW + timedelta(days=30)


# ---------------------------------------------------------------------------
# PARTIAL / MISS / MISCONCEPTION
# ---------------------------------------------------------------------------

def test_partial_schedules_immediate_repair_at_one_day():
    scheduler = BaselineScheduler()
    state = fresh_state()
    state = scheduler.next_due(state, outcome="PASS", now=NOW)  # get to 1d rung
    state = scheduler.next_due(state, outcome="PARTIAL", now=NOW)
    assert state.due_at == NOW + timedelta(days=1)
    assert state.failure_streak == 1
    assert state.lapse_count == 1


def test_miss_schedules_immediate_repair_at_one_day():
    scheduler = BaselineScheduler()
    state = fresh_state()
    state = scheduler.next_due(state, outcome="MISS", now=NOW)
    assert state.due_at == NOW + timedelta(days=1)
    assert state.failure_streak == 1


def test_miss_after_pass_ladder_resets_ladder_to_one_day():
    scheduler = BaselineScheduler()
    state = fresh_state()
    for _ in range(3):  # ladder at 7d
        state = scheduler.next_due(state, outcome="PASS", now=NOW)
    state = scheduler.next_due(state, outcome="MISS", now=NOW)
    assert state.due_at == NOW + timedelta(days=1)
    # subsequent PASS restarts from the bottom of the ladder, not from 7d
    state = scheduler.next_due(state, outcome="PASS", now=NOW)
    assert state.due_at == NOW + timedelta(days=1)


def test_misconception_restarts_ladder_from_one_day():
    scheduler = BaselineScheduler()
    state = fresh_state()
    for _ in range(4):  # ladder at 14d
        state = scheduler.next_due(state, outcome="PASS", now=NOW)
    state = scheduler.next_due(state, outcome="MISCONCEPTION", now=NOW)
    assert state.due_at == NOW + timedelta(days=1)
    assert state.failure_streak == 1
    assert state.lapse_count == 1


def test_skipped_does_not_change_due_at_or_streaks():
    scheduler = BaselineScheduler()
    state = fresh_state()
    state = scheduler.next_due(state, outcome="PASS", now=NOW)
    due_before = state.due_at
    streak_before = state.failure_streak
    result = scheduler.next_due(state, outcome="SKIPPED", now=NOW)
    assert result.due_at == due_before
    assert result.failure_streak == streak_before
    assert result.last_outcome == "PASS"  # SKIPPED doesn't overwrite last real outcome


# ---------------------------------------------------------------------------
# Leech detection (plan section 10.4)
# ---------------------------------------------------------------------------

def test_three_consecutive_failures_triggers_leech_intervention():
    scheduler = BaselineScheduler()
    state = fresh_state()
    for outcome in ("MISS", "MISCONCEPTION"):
        state = scheduler.next_due(state, outcome=outcome, now=NOW)
        assert state.intervention_required is False
    state = scheduler.next_due(state, outcome="PARTIAL", now=NOW)
    assert state.intervention_required is True
    assert state.active is False


def test_pass_breaks_consecutive_failure_streak_and_avoids_leech():
    scheduler = BaselineScheduler()
    state = fresh_state()
    state = scheduler.next_due(state, outcome="MISS", now=NOW)
    state = scheduler.next_due(state, outcome="MISS", now=NOW)
    state = scheduler.next_due(state, outcome="PASS", now=NOW)
    state = scheduler.next_due(state, outcome="MISS", now=NOW)
    assert state.intervention_required is False
    assert state.failure_streak == 1


def test_four_of_last_five_non_pass_triggers_leech_even_without_streak_of_three():
    scheduler = BaselineScheduler()
    state = fresh_state()
    # MISS, PASS, MISS, PARTIAL, MISS -> 4 non-PASS of last 5, no run of 3
    for outcome in ("MISS", "PASS", "MISS", "PARTIAL"):
        state = scheduler.next_due(state, outcome=outcome, now=NOW)
        assert state.intervention_required is False
    state = scheduler.next_due(state, outcome="MISS", now=NOW)
    assert state.intervention_required is True
    assert state.active is False


def test_leech_state_suspends_auto_due_until_manual_repair_confirmed():
    scheduler = BaselineScheduler()
    state = fresh_state()
    for outcome in ("MISS", "MISCONCEPTION", "MISS"):
        state = scheduler.next_due(state, outcome=outcome, now=NOW)
    assert state.active is False
    assert state.intervention_required is True
    # while suspended, further outcomes don't get scheduled onto the ladder
    with pytest.raises(ValueError):
        scheduler.next_due(state, outcome="MISS", now=NOW)


def test_confirm_repair_reactivates_and_restarts_ladder_from_one_day():
    scheduler = BaselineScheduler()
    state = fresh_state()
    for outcome in ("MISS", "MISCONCEPTION", "MISS"):
        state = scheduler.next_due(state, outcome=outcome, now=NOW)
    assert state.active is False
    repaired = scheduler.confirm_repair(state, now=NOW)
    assert repaired.active is True
    assert repaired.intervention_required is False
    assert repaired.failure_streak == 0
    # next PASS after repair starts back at 1d, proving the ladder restarted
    result = scheduler.next_due(repaired, outcome="PASS", now=NOW)
    assert result.due_at == NOW + timedelta(days=1)


def test_confirm_repair_on_non_leeched_item_raises():
    scheduler = BaselineScheduler()
    state = fresh_state()
    state = scheduler.next_due(state, outcome="PASS", now=NOW)
    with pytest.raises(ValueError):
        scheduler.confirm_repair(state, now=NOW)
