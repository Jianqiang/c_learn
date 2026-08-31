"""Application recording + concept evidence-gate service (plan section 6.4,
7.2 #applications, 8's services table).

This module is the *only* sanctioned path for moving a concept across
USABLE / STABLE / RETIRED / REACTIVATED. ConceptRepository.set_status()
still owns the raw adjacency check (can concept X even legally move from
its current state to the target state?) and the status_events write, but
it has no idea what "evidence" means -- that is a workflow-level judgement
plan 6.4 assigns to this service, not to the repository layer. Calling
ConceptRepository.set_status() directly for USABLE/STABLE bypasses the
gate entirely, which is exactly the "系统不得静默改变 concept 状态"
violation plan 6.3 forbids; callers (CLI, future web layer) must go through
promote_to_usable() / promote_to_stable() / retire() / reactivate() instead.

Evidence gate proxies (plan 6.4 is written in terms a human applies during a
real session; this is the mechanical proxy this v1 implementation checks
against the attempts/applications tables so the gate cannot be bypassed by
merely calling set_status() with a hand-written reason string):

USABLE (ACTIVE -> USABLE)
    "至少一个核心 rubric atom 通过" -> proxy: at least one attempt on one of
        the concept's items has outcome PASS or PARTIAL (rubric.py's own
        PASS/PARTIAL/MISS/MISCONCEPTION vocabulary; PARTIAL still means at
        least one must_understand atom was satisfied per aggregate_outcome()).
    "一个 evidence record" -> proxy: at least one applications row for this
        concept exists, at either evidence_level (STRONG from real research/
        case, or PARTIAL from a declared syllabus output) -- plan 6.4
        explicitly allows partial evidence to unlock USABLE, with the
        "待真实 transfer" caveat left to the UI/CLI layer to display.

STABLE (USABLE -> STABLE)
    "delayed recall 通过" -> proxy: at least one attempt with outcome=PASS
        on an item attempted during a session_type='recall' session, where
        that same item also has an earlier non-recall attempt predating the
        recall PASS (the session type SessionService already uses to
        distinguish recall practice from ordinary drills). The prior-
        exposure requirement closes a 2026-08-30 audit finding: without it, a
        recall session run as literally the first-ever interaction with an
        item satisfied "delayed recall passed" even though nothing had
        actually been recalled *after a delay* -- there was no earlier
        learning episode to recall from.
    "两个不同 case 正确调用，或用户明确确认足够稳定" -> proxy: at least two
        applications rows with result='SUCCESS' whose `reference` values
        (trimmed of surrounding whitespace) are distinct, OR the caller
        passes user_confirms_stable=True (the plan's explicit escape hatch
        for when a user judges stability directly rather than via counted
        cases). Rows with no reference (NULL or blank) are never deduplicated
        against each other -- each still counts as its own case -- both for
        back-compat with existing callers that never set `reference`, and
        because an empty reference carries no information that two rows
        actually describe the *same* case. This distinctness requirement
        closes a 2026-08-30 audit finding: submitting the same reference
        text (e.g. the same research episode) twice previously satisfied
        "two different cases correctly applied."
    "没有未修复的 recurring misconception" -> proxy: for every item belonging
        to the concept, that item's most-recently-submitted attempt (if any)
        is not itself MISCONCEPTION. A MISCONCEPTION followed by a later
        PASS/PARTIAL/MISS attempt on the same item counts as repaired.
    "至少一个 strong application" -> proxy: at least one applications row
        with evidence_level='STRONG' for this concept.

RETIRED (STABLE -> RETIRED)
    "用户确认暂不主动复习" -> proxy: caller must supply a non-empty, non-
        whitespace `reason`. There is no automated signal for "user has
        decided this"; requiring an explicit reason string is the mechanical
        stand-in for that confirmation and keeps a human-readable record in
        status_events of *why* review stopped.

REACTIVATED (RETIRED -> REACTIVATED)
    Plan 6.3 lists REACTIVATED as re-entering the active queue "因失败、
    研究需求或知识变化" but attaches no evidence gate of its own (unlike
    USABLE/STABLE); it is deliberately easier to re-open a concept than to
    first close it, so this call is a plain adjacency-checked delegation to
    ConceptRepository.set_status() with no extra gate.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from learning_os.repositories import CONCEPT_TRANSITIONS, Concept, ConceptRepository, InvalidTransitionError

VALID_EVIDENCE_LEVELS = {"PARTIAL", "STRONG"}
VALID_RESULTS = {"SUCCESS", "PARTIAL", "FAILURE", "UNASSESSED"}

_RUBRIC_ATOM_PASS_OUTCOMES = {"PASS", "PARTIAL"}


class EvidenceGateError(Exception):
    """Raised when a USABLE/STABLE/RETIRED promotion is attempted without
    satisfying the plan 6.4 evidence gate for that transition. Distinct from
    InvalidTransitionError (repositories.py), which only ever fires for a
    transition the workflow adjacency map does not allow at all -- this
    error means the adjacency is fine but the evidence behind it is not."""


@dataclass
class Application:
    id: int
    concept_id: int
    output_id: Optional[int]
    reference_type: Optional[str]
    reference: Optional[str]
    note: Optional[str]
    evidence: Optional[str]
    evidence_level: str
    result: str
    created_at: str


_APPLICATION_COLUMNS = (
    "id, concept_id, output_id, reference_type, reference, note, evidence, "
    "evidence_level, result, created_at"
)


def _row_to_application(row) -> Application:
    return Application(
        id=row[0], concept_id=row[1], output_id=row[2], reference_type=row[3],
        reference=row[4], note=row[5], evidence=row[6], evidence_level=row[7],
        result=row[8], created_at=row[9],
    )


class ApplicationService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._concepts = ConceptRepository(conn)

    # -- applications --------------------------------------------------------

    def record_application(
        self,
        *,
        concept_id: int,
        evidence_level: str,
        output_id: Optional[int] = None,
        reference_type: Optional[str] = None,
        reference: Optional[str] = None,
        note: Optional[str] = None,
        evidence: Optional[str] = None,
        result: str = "UNASSESSED",
    ) -> Application:
        if evidence_level not in VALID_EVIDENCE_LEVELS:
            raise ValueError(f"invalid evidence_level: {evidence_level!r}")
        if result not in VALID_RESULTS:
            raise ValueError(f"invalid result: {result!r}")
        if evidence_level == "STRONG" and output_id is not None:
            raise ValueError(
                "STRONG evidence must come from a real research/case "
                "application, not a syllabus output (plan 6.4: syllabus "
                "output is partial evidence by construction) -- record this "
                "with evidence_level='PARTIAL' instead"
            )
        self._concepts.get(concept_id)  # raises KeyError if the concept does not exist

        cur = self._conn.execute(
            "INSERT INTO applications "
            "(concept_id, output_id, reference_type, reference, note, "
            "evidence, evidence_level, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                concept_id, output_id, reference_type, reference, note,
                evidence, evidence_level, result,
            ),
        )
        self._conn.commit()
        return self.get_application(cur.lastrowid)

    def get_application(self, application_id: int) -> Application:
        row = self._conn.execute(
            f"SELECT {_APPLICATION_COLUMNS} FROM applications WHERE id=?",
            (application_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"application {application_id} not found")
        return _row_to_application(row)

    def list_applications(self, concept_id: int) -> list[Application]:
        rows = self._conn.execute(
            f"SELECT {_APPLICATION_COLUMNS} FROM applications "
            "WHERE concept_id=? ORDER BY id ASC",
            (concept_id,),
        ).fetchall()
        return [_row_to_application(row) for row in rows]

    # -- evidence gate helpers -----------------------------------------------

    def _has_rubric_atom_pass(self, concept_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM attempts a JOIN items i ON a.item_id = i.id "
            "WHERE i.concept_id = ? AND a.outcome IN (?, ?) LIMIT 1",
            (concept_id, *sorted(_RUBRIC_ATOM_PASS_OUTCOMES)),
        ).fetchone()
        return row is not None

    def _has_delayed_recall_pass(self, concept_id: int) -> bool:
        # Requires a recall-session PASS attempt on an item that *also* has
        # an earlier non-recall attempt on the same item (attempts.id is
        # monotonically increasing with insertion order, so a2.id < a.id is
        # a reliable "happened before" check within this DB). Without this
        # prior-exposure requirement, a recall session run as the first-ever
        # interaction with an item would satisfy "delayed recall passed"
        # even though nothing had actually been recalled after a delay --
        # closes a 2026-08-30 audit finding.
        row = self._conn.execute(
            "SELECT 1 FROM attempts a "
            "JOIN items i ON a.item_id = i.id "
            "JOIN sessions s ON a.session_id = s.id "
            "WHERE i.concept_id = ? AND s.session_type = 'recall' "
            "AND a.outcome = 'PASS' "
            "AND EXISTS ("
            "    SELECT 1 FROM attempts a2 "
            "    JOIN sessions s2 ON a2.session_id = s2.id "
            "    WHERE a2.item_id = a.item_id AND s2.session_type != 'recall' "
            "    AND a2.id < a.id"
            ") LIMIT 1",
            (concept_id,),
        ).fetchone()
        return row is not None

    def _successful_case_count(self, concept_id: int) -> int:
        # Deduplicate by trimmed `reference` text so the same case (e.g. the
        # same research episode) submitted twice does not count as two
        # distinct cases -- closes a 2026-08-30 audit finding. Rows with no
        # reference (NULL or blank) are never merged with each other: each
        # still counts as its own case, both for back-compat with callers
        # that never set `reference` and because a blank reference carries
        # no information that two rows describe the same case.
        rows = self._conn.execute(
            "SELECT reference FROM applications WHERE concept_id=? AND result='SUCCESS'",
            (concept_id,),
        ).fetchall()
        distinct_references: set[str] = set()
        blank_reference_count = 0
        for (reference,) in rows:
            if reference is None or not reference.strip():
                blank_reference_count += 1
            else:
                distinct_references.add(reference.strip())
        return len(distinct_references) + blank_reference_count

    def _has_strong_application(self, concept_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM applications WHERE concept_id=? AND evidence_level='STRONG' LIMIT 1",
            (concept_id,),
        ).fetchone()
        return row is not None

    def _has_any_application(self, concept_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM applications WHERE concept_id=? LIMIT 1",
            (concept_id,),
        ).fetchone()
        return row is not None

    def _has_unresolved_misconception(self, concept_id: int) -> bool:
        """True if any item belonging to this concept has its most recently
        *submitted* attempt still marked MISCONCEPTION. A later PASS/PARTIAL/
        MISS attempt on the same item after the MISCONCEPTION counts as a
        repair, matching plan 6.4's "recurring" framing -- one historical
        MISCONCEPTION that was subsequently corrected should not permanently
        block STABLE."""
        item_rows = self._conn.execute(
            "SELECT id FROM items WHERE concept_id=?", (concept_id,)
        ).fetchall()
        for (item_id,) in item_rows:
            last = self._conn.execute(
                "SELECT outcome FROM attempts WHERE item_id=? AND submitted_at IS NOT NULL "
                "ORDER BY id DESC LIMIT 1",
                (item_id,),
            ).fetchone()
            if last is not None and last[0] == "MISCONCEPTION":
                return True
        return False

    # -- gated promotions -----------------------------------------------------

    def promote_to_usable(
        self, concept_id: int, *, reason: Optional[str] = None, actor: str = "user",
    ) -> Concept:
        current = self._concepts.get(concept_id)
        # Check the adjacency map ourselves first (rather than letting the
        # eventual set_status() call discover it) so an illegal source state
        # (e.g. QUEUED -> USABLE) raises InvalidTransitionError immediately,
        # before we spend effort computing evidence gates that would be moot.
        if "USABLE" not in CONCEPT_TRANSITIONS.get(current.workflow_status, set()):
            raise InvalidTransitionError(
                f"concept cannot transition from {current.workflow_status} to USABLE"
            )

        problems = []
        if not self._has_rubric_atom_pass(concept_id):
            problems.append("no attempt with outcome PASS/PARTIAL on any item of this concept")
        if not self._has_any_application(concept_id):
            problems.append("no applications record (STRONG or PARTIAL) for this concept")
        if problems:
            raise EvidenceGateError(
                f"concept {concept_id} cannot reach USABLE yet: " + "; ".join(problems)
            )

        return self._concepts.set_status(concept_id, "USABLE", reason=reason, actor=actor)

    def promote_to_stable(
        self,
        concept_id: int,
        *,
        reason: Optional[str] = None,
        actor: str = "user",
        user_confirms_stable: bool = False,
    ) -> Concept:
        current = self._concepts.get(concept_id)
        if "STABLE" not in CONCEPT_TRANSITIONS.get(current.workflow_status, set()):
            raise InvalidTransitionError(
                f"concept cannot transition from {current.workflow_status} to STABLE"
            )

        problems = []
        if not self._has_delayed_recall_pass(concept_id):
            problems.append("no PASS attempt recorded during a recall session")
        if not user_confirms_stable and self._successful_case_count(concept_id) < 2:
            problems.append(
                "fewer than 2 SUCCESS applications and user_confirms_stable=False"
            )
        if self._has_unresolved_misconception(concept_id):
            problems.append(
                "at least one item's most recent submitted attempt is still MISCONCEPTION"
            )
        if not self._has_strong_application(concept_id):
            problems.append("no STRONG evidence_level application for this concept")
        if problems:
            raise EvidenceGateError(
                f"concept {concept_id} cannot reach STABLE yet: " + "; ".join(problems)
            )

        return self._concepts.set_status(concept_id, "STABLE", reason=reason, actor=actor)

    def retire(self, concept_id: int, *, reason: str, actor: str = "user") -> Concept:
        current = self._concepts.get(concept_id)
        if "RETIRED" not in CONCEPT_TRANSITIONS.get(current.workflow_status, set()):
            raise InvalidTransitionError(
                f"concept cannot transition from {current.workflow_status} to RETIRED"
            )

        if reason is None or not reason.strip():
            raise EvidenceGateError(
                "RETIRED requires an explicit, non-empty reason recording the "
                "user's confirmation that active review should stop "
                "(plan 6.4: RETIRED = 用户确认暂不主动复习)"
            )

        return self._concepts.set_status(concept_id, "RETIRED", reason=reason, actor=actor)

    def reactivate(
        self, concept_id: int, *, reason: Optional[str] = None, actor: str = "user",
    ) -> Concept:
        # No plan 6.4 evidence gate attached to REACTIVATED; delegate
        # straight to the repository so its adjacency map is the sole
        # authority (raises InvalidTransitionError for an illegal source
        # state) and status_events still records the reason given.
        return self._concepts.set_status(concept_id, "REACTIVATED", reason=reason, actor=actor)
