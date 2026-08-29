"""Next Best Actions recommendation service (plan section 11).

Plan 11 is explicit that v1 must be a deterministic priority table, not a
scoring formula ("v1 不使用复杂公式或机器学习 ranking"; "不得把 importance ×
relevance × gap / time 展示成伪精确结论"). RecommendationService.recommend()
walks four fixed tiers, in order, and stops collecting once max_actions (plan
11: "输出 2-4 个 action") is reached:

    P1  explicit research dependency
        Caller-supplied concept_ids (plan 11's "当前 research/application
        明确依赖的 item", same idea as ReviewService.select_batch()'s
        dependency_item_ids, but at concept granularity here since the
        Next Best Action is "go drill/apply this concept", not "answer this
        one item"). No further gate: if the caller says a concept is a
        current dependency, it is P1 by construction. Raises KeyError for
        an unknown concept_id -- silently dropping a caller-asserted
        dependency would hide a caller bug (typo'd id) as "nothing to do".

    P2  current ACTIVE concept repair
        Every concept with workflow_status='ACTIVE' that has at least one
        attempt with outcome in {MISS, MISCONCEPTION} on any of its items
        (proxy for plan 11's "当前 ACTIVE concept 的失败") is a P2 action_type
        'repair'. Only the concept's *most recent* attempt need not be a
        failure -- plan 11 says "失败", not "最近一次失败"; any recorded
        failure on an ACTIVE concept is a standing repair candidate until
        the concept moves on or the item's history changes.

    P3  important concept with recent failure/high-confidence error
        Concepts with importance IS NOT NULL and workflow_status NOT IN
        ('QUEUED', 'RETIRED') (QUEUED hasn't started, RETIRED is explicitly
        parked -- plan 6.4/6.3 -- so recommending review of either would
        contradict the workflow state) qualify if they have either:
          - an attempt with outcome in {MISS, MISCONCEPTION}, OR
          - a PARTIAL/MISS/MISCONCEPTION attempt with
            confidence >= high_confidence_threshold (default
            DEFAULT_HIGH_CONFIDENCE_THRESHOLD=0.8; plan 9.4's own
            high-confidence-error framing has no fixed cutoff, so this is
            a documented, overridable proxy rather than a plan-mandated
            number).
        ACTIVE concepts satisfying P3's condition are absorbed into P2
        instead (see dedup below) since P2 already covers them with a
        stronger and more specific reason.

    P4  approved QUEUED source
        sources with status='QUEUED', resource_mode='consumable',
        pace_mode='self_paced', scope_confirmed=1 (plan 11's explicit
        filter list, restated -- and re-checked here even though
        SourceRepository.set_status() already gates entry into QUEUED,
        because this recommender reads sources directly and must not
        silently recommend a row written by another path, e.g. bulk
        import, that bypassed that gate) AND module.phase <= current_phase
        (focus_state; defaults to 1 if no focus_state row exists yet, same
        as ConceptRepository/FocusRepository's implicit v1 default) AND
        ReviewService.review_load(now) < REVIEW_LOAD_GATE (0.8, from plan
        11's literal "review_load < 0.8").

Dedup (plan 11: "同一 target 的重复推荐需要去重"): a (target_type, target_id)
pair is only ever emitted once, at the highest-priority (lowest-numbered)
tier it qualifies for -- collection proceeds P1 -> P2 -> P3 -> P4 and each
tier skips any target already claimed by an earlier tier.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from learning_os.repositories import ConceptRepository, FocusRepository
from learning_os.services.review_service import ReviewService

DEFAULT_CONCEPT_ACTION_MINUTES = 15
DEFAULT_SOURCE_ACTION_MINUTES = 20
DEFAULT_HIGH_CONFIDENCE_THRESHOLD = 0.8
REVIEW_LOAD_GATE = 0.8
DEFAULT_MAX_ACTIONS = 4

_FAILURE_OUTCOMES = {"MISS", "MISCONCEPTION"}
_HIGH_CONFIDENCE_ERROR_OUTCOMES = {"PARTIAL", "MISS", "MISCONCEPTION"}


@dataclass
class Action:
    priority: int
    action_type: str
    target_type: str
    target_id: int
    estimated_minutes: int
    reason: str
    expected_output: str


class RecommendationService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._concepts = ConceptRepository(conn)
        self._focus = FocusRepository(conn)
        self._review = ReviewService(conn)

    def recommend(
        self,
        *,
        now: datetime,
        dependency_concept_ids: Iterable[int] = (),
        max_actions: int = DEFAULT_MAX_ACTIONS,
        high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    ) -> list[Action]:
        claimed: set[tuple[str, int]] = set()
        actions: list[Action] = []

        for concept_id in dict.fromkeys(dependency_concept_ids):  # de-dup, preserve order
            if len(actions) >= max_actions:
                return actions[:max_actions]
            concept = self._concepts.get(concept_id)  # raises KeyError if unknown
            key = ("concept", concept.id)
            if key in claimed:
                continue
            claimed.add(key)
            actions.append(
                Action(
                    priority=1,
                    action_type="drill",
                    target_type="concept",
                    target_id=concept.id,
                    estimated_minutes=DEFAULT_CONCEPT_ACTION_MINUTES,
                    reason="explicit research/application dependency",
                    expected_output=f"drill result for '{concept.name}' unblocking the dependent work",
                )
            )

        if len(actions) < max_actions:
            for concept_id, concept_name in self._active_concepts_with_failure():
                if len(actions) >= max_actions:
                    break
                key = ("concept", concept_id)
                if key in claimed:
                    continue
                claimed.add(key)
                actions.append(
                    Action(
                        priority=2,
                        action_type="repair",
                        target_type="concept",
                        target_id=concept_id,
                        estimated_minutes=DEFAULT_CONCEPT_ACTION_MINUTES,
                        reason="current ACTIVE concept has a recorded failure needing repair",
                        expected_output=f"repaired attempt (PASS/PARTIAL) for '{concept_name}'",
                    )
                )

        if len(actions) < max_actions:
            for concept_id, concept_name, sub_reason in self._important_concepts_with_error(
                high_confidence_threshold=high_confidence_threshold,
            ):
                if len(actions) >= max_actions:
                    break
                key = ("concept", concept_id)
                if key in claimed:
                    continue
                claimed.add(key)
                actions.append(
                    Action(
                        priority=3,
                        action_type="review",
                        target_type="concept",
                        target_id=concept_id,
                        estimated_minutes=DEFAULT_CONCEPT_ACTION_MINUTES,
                        reason=f"important concept with {sub_reason}",
                        expected_output=f"corrected attempt for '{concept_name}'",
                    )
                )

        if len(actions) < max_actions:
            current_phase = self._current_phase()
            review_load = self._review.review_load(now=now)
            if review_load < REVIEW_LOAD_GATE:
                for source_id, title, estimated_minutes, output_hint in self._approved_queued_sources(
                    current_phase=current_phase,
                ):
                    if len(actions) >= max_actions:
                        break
                    key = ("source", source_id)
                    if key in claimed:
                        continue
                    claimed.add(key)
                    actions.append(
                        Action(
                            priority=4,
                            action_type="learn",
                            target_type="source",
                            target_id=source_id,
                            estimated_minutes=estimated_minutes or DEFAULT_SOURCE_ACTION_MINUTES,
                            reason="approved QUEUED source within the current phase and review budget",
                            expected_output=output_hint or f"notes/summary from '{title}'",
                        )
                    )

        return actions[:max_actions]

    # -- tier queries ----------------------------------------------------

    def _active_concepts_with_failure(self) -> list[tuple[int, str]]:
        rows = self._conn.execute(
            "SELECT DISTINCT c.id, c.name FROM concepts c "
            "JOIN items i ON i.concept_id = c.id "
            "JOIN attempts a ON a.item_id = i.id "
            "WHERE c.workflow_status = 'ACTIVE' "
            "AND a.outcome IN (?, ?) "
            "ORDER BY c.id ASC",
            tuple(sorted(_FAILURE_OUTCOMES)),
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def _important_concepts_with_error(
        self, *, high_confidence_threshold: float,
    ) -> list[tuple[int, str, str]]:
        rows = self._conn.execute(
            "SELECT c.id, c.name, a.outcome, a.confidence "
            "FROM concepts c "
            "JOIN items i ON i.concept_id = c.id "
            "JOIN attempts a ON a.item_id = i.id "
            "WHERE c.importance IS NOT NULL "
            "AND c.workflow_status NOT IN ('QUEUED', 'RETIRED') "
            "ORDER BY c.id ASC, a.id ASC"
        ).fetchall()
        result: dict[int, tuple[str, str]] = {}
        for concept_id, name, outcome, confidence in rows:
            if concept_id in result:
                continue
            if outcome in _FAILURE_OUTCOMES:
                result[concept_id] = (name, "recent failure")
            elif (
                outcome in _HIGH_CONFIDENCE_ERROR_OUTCOMES
                and confidence is not None
                and confidence >= high_confidence_threshold
            ):
                result[concept_id] = (name, "high-confidence error")
        return [(cid, name, reason) for cid, (name, reason) in result.items()]

    def _current_phase(self) -> int:
        focus = self._focus.get_current()
        return focus.current_phase if focus is not None else 1

    def _approved_queued_sources(
        self, *, current_phase: int,
    ) -> list[tuple[int, str, Optional[int], Optional[str]]]:
        rows = self._conn.execute(
            "SELECT s.id, s.title, s.estimated_minutes, s.output_hint "
            "FROM sources s JOIN modules m ON m.id = s.module_id "
            "WHERE s.status = 'QUEUED' "
            "AND s.resource_mode = 'consumable' "
            "AND s.pace_mode = 'self_paced' "
            "AND s.scope_confirmed = 1 "
            "AND m.phase <= ? "
            "ORDER BY s.id ASC",
            (current_phase,),
        ).fetchall()
        return [(row[0], row[1], row[2], row[3]) for row in rows]
