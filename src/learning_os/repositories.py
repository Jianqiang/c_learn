"""Repository layer: the only place that reads/writes modules, sources,
concepts, concept_sources, and focus_state, and the only place that knows
the state-machine rules from plan section 6.

Every set_status() call is atomic (row update + status_events insert happen
in the same transaction) and validates the transition against an explicit
adjacency map before touching the row, so an invalid request never mutates
state and always leaves a clear reason for the rejection.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


class InvalidTransitionError(ValueError):
    """Raised when a status transition is not allowed by the workflow."""


def _record_status_event(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    from_status: Optional[str],
    to_status: str,
    reason: Optional[str],
    actor: str = "user",
) -> None:
    conn.execute(
        "INSERT INTO status_events "
        "(entity_type, entity_id, from_status, to_status, reason, actor) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (entity_type, entity_id, from_status, to_status, reason, actor),
    )


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

MODULE_TRANSITIONS = {
    "AVAILABLE": {"ACTIVE", "ARCHIVED"},
    "ACTIVE": {"PAUSED", "ARCHIVED"},
    "PAUSED": {"ACTIVE", "ARCHIVED"},
    "ARCHIVED": set(),  # terminal
}


@dataclass
class Module:
    id: int
    slug: str
    name: str
    phase: int
    importance: Optional[str]
    status: str
    notes: Optional[str]


class ModuleRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(
        self, *, slug: str, name: str, phase: int,
        importance: Optional[str] = None, notes: Optional[str] = None,
    ) -> Module:
        cur = self._conn.execute(
            "INSERT INTO modules (slug, name, phase, importance, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (slug, name, phase, importance, notes),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, module_id: int) -> Module:
        row = self._conn.execute(
            "SELECT id, slug, name, phase, importance, status, notes "
            "FROM modules WHERE id=?",
            (module_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"module {module_id} not found")
        return Module(*row)

    def get_by_slug(self, slug: str) -> Module:
        row = self._conn.execute(
            "SELECT id, slug, name, phase, importance, status, notes "
            "FROM modules WHERE slug=?",
            (slug,),
        ).fetchone()
        if row is None:
            raise KeyError(f"module '{slug}' not found")
        return Module(*row)

    def set_status(
        self, module_id: int, to_status: str, reason: Optional[str] = None,
        actor: str = "user",
    ) -> Module:
        current = self.get(module_id)
        allowed = MODULE_TRANSITIONS.get(current.status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(
                f"module cannot transition from {current.status} to {to_status}"
            )
        self._conn.execute(
            "UPDATE modules SET status=?, updated_at=datetime('now') WHERE id=?",
            (to_status, module_id),
        )
        _record_status_event(
            self._conn, "module", module_id, current.status, to_status, reason, actor,
        )
        self._conn.commit()
        return self.get(module_id)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SOURCE_TRANSITIONS = {
    "PROPOSED": {"QUEUED", "VISIBLE", "ARCHIVED"},
    "QUEUED": {"OPEN", "ARCHIVED"},
    "VISIBLE": {"ARCHIVED"},
    "OPEN": {"CONSUMED", "SKIPPED", "ARCHIVED"},
    "CONSUMED": {"ARCHIVED"},
    "SKIPPED": {"ARCHIVED"},
    "ARCHIVED": set(),
}


@dataclass
class Source:
    id: int
    module_id: int
    slug: Optional[str]
    title: str
    type: str
    status: str
    resource_mode: str
    pace_mode: str
    scope_note: Optional[str]
    scope_confirmed: bool


class SourceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(
        self, *, module_id: int, title: str, type: str,
        resource_mode: str = "consumable", pace_mode: str = "self_paced",
        slug: Optional[str] = None, url_or_path: Optional[str] = None,
        estimated_minutes: Optional[int] = None, priority: Optional[str] = None,
        scope_note: Optional[str] = None, scope_confirmed: bool = False,
        output_hint: Optional[str] = None, source_file: Optional[str] = None,
        source_line: Optional[int] = None, content_hash: Optional[str] = None,
    ) -> Source:
        cur = self._conn.execute(
            "INSERT INTO sources "
            "(module_id, slug, title, type, url_or_path, estimated_minutes, "
            "priority, resource_mode, pace_mode, scope_note, scope_confirmed, "
            "output_hint, source_file, source_line, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                module_id, slug, title, type, url_or_path, estimated_minutes,
                priority, resource_mode, pace_mode, scope_note,
                int(scope_confirmed), output_hint, source_file, source_line,
                content_hash,
            ),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, source_id: int) -> Source:
        row = self._conn.execute(
            "SELECT id, module_id, slug, title, type, status, resource_mode, "
            "pace_mode, scope_note, scope_confirmed FROM sources WHERE id=?",
            (source_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"source {source_id} not found")
        return self._row_to_source(row)

    def get_by_slug(self, slug: str) -> Source:
        # Added for CLI wiring (`learn learn <source-slug>`, plan 12.1):
        # ModuleRepository/ConceptRepository already resolve their CLI-facing
        # targets by slug; sources need the same lookup rather than forcing
        # every caller to know the numeric id. Sources are the only content
        # type with a nullable slug column (plan 7.2: not every source is
        # meant to be addressed directly), so an existing row with slug=NULL
        # is treated the same as "not found" -- SQL `slug=?` never matches
        # NULL, which is exactly the semantics we want here.
        row = self._conn.execute(
            "SELECT id, module_id, slug, title, type, status, resource_mode, "
            "pace_mode, scope_note, scope_confirmed FROM sources WHERE slug=?",
            (slug,),
        ).fetchone()
        if row is None:
            raise KeyError(f"source '{slug}' not found")
        return self._row_to_source(row)

    @staticmethod
    def _row_to_source(row) -> Source:
        return Source(
            id=row[0], module_id=row[1], slug=row[2], title=row[3], type=row[4],
            status=row[5], resource_mode=row[6], pace_mode=row[7],
            scope_note=row[8], scope_confirmed=bool(row[9]),
        )

    def set_status(
        self, source_id: int, to_status: str, reason: Optional[str] = None,
        actor: str = "user",
    ) -> Source:
        current = self.get(source_id)
        allowed = SOURCE_TRANSITIONS.get(current.status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(
                f"source cannot transition from {current.status} to {to_status}"
            )
        if to_status == "QUEUED":
            # Plan 6.2: QUEUED is "仅适用于 resource_mode=consumable、
            # pace_mode=self_paced 的 source" -- reference/sensor sources
            # go to VISIBLE instead, external_paced sources are navigation
            # only and never enter the fixed-interval scheduler. Section
            # 5.3 additionally requires an explicit scope_note/
            # scope_confirmed decision before a source starts consuming
            # normal drill/review budget, and QUEUED (user approval to
            # start working through it) is the natural gate for that
            # decision -- so we check it here rather than only at OPEN.
            problems = []
            if current.resource_mode != "consumable":
                problems.append(
                    f"resource_mode={current.resource_mode!r} (must be 'consumable')"
                )
            if current.pace_mode != "self_paced":
                problems.append(
                    f"pace_mode={current.pace_mode!r} (must be 'self_paced')"
                )
            if not current.scope_confirmed:
                problems.append("scope_confirmed=False")
            if problems:
                raise InvalidTransitionError(
                    "source cannot enter QUEUED: " + "; ".join(problems)
                )
        self._conn.execute(
            "UPDATE sources SET status=?, updated_at=datetime('now') WHERE id=?",
            (to_status, source_id),
        )
        _record_status_event(
            self._conn, "source", source_id, current.status, to_status, reason, actor,
        )
        self._conn.commit()
        return self.get(source_id)


# ---------------------------------------------------------------------------
# Concepts
# ---------------------------------------------------------------------------

CONCEPT_TRANSITIONS = {
    "QUEUED": {"ACTIVE"},
    "ACTIVE": {"USABLE"},
    "USABLE": {"STABLE"},
    "STABLE": {"RETIRED"},
    "RETIRED": {"REACTIVATED"},
    "REACTIVATED": {"ACTIVE"},
}


@dataclass
class Concept:
    id: int
    module_id: int
    slug: str
    name: str
    workflow_status: str


class ConceptRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(
        self, *, module_id: int, slug: str, name: str,
        importance: Optional[str] = None, description: Optional[str] = None,
        research_relevance: Optional[str] = None,
    ) -> Concept:
        cur = self._conn.execute(
            "INSERT INTO concepts "
            "(module_id, slug, name, importance, description, research_relevance) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (module_id, slug, name, importance, description, research_relevance),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, concept_id: int) -> Concept:
        row = self._conn.execute(
            "SELECT id, module_id, slug, name, workflow_status "
            "FROM concepts WHERE id=?",
            (concept_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"concept {concept_id} not found")
        return Concept(*row)

    def get_by_slug(self, slug: str) -> Concept:
        row = self._conn.execute(
            "SELECT id, module_id, slug, name, workflow_status "
            "FROM concepts WHERE slug=?",
            (slug,),
        ).fetchone()
        if row is None:
            raise KeyError(f"concept '{slug}' not found")
        return Concept(*row)

    def set_status(
        self, concept_id: int, to_status: str, reason: Optional[str] = None,
        actor: str = "user",
    ) -> Concept:
        current = self.get(concept_id)
        allowed = CONCEPT_TRANSITIONS.get(current.workflow_status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(
                f"concept cannot transition from {current.workflow_status} "
                f"to {to_status}"
            )
        self._conn.execute(
            "UPDATE concepts SET workflow_status=?, updated_at=datetime('now') "
            "WHERE id=?",
            (to_status, concept_id),
        )
        _record_status_event(
            self._conn, "concept", concept_id, current.workflow_status,
            to_status, reason, actor,
        )
        self._conn.commit()
        return self.get(concept_id)

    def link_source(
        self, concept_id: int, source_id: int,
        relationship: Optional[str] = None, notes: Optional[str] = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO concept_sources (concept_id, source_id, relationship, notes) "
            "VALUES (?, ?, ?, ?)",
            (concept_id, source_id, relationship, notes),
        )
        self._conn.commit()


# ---------------------------------------------------------------------------
# Focus state (single active row)
# ---------------------------------------------------------------------------

@dataclass
class Focus:
    id: int
    current_phase: int
    target_type: Optional[str]
    target_id: Optional[int]
    rationale: Optional[str]


class FocusRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_current(self) -> Optional[Focus]:
        row = self._conn.execute(
            "SELECT id, current_phase, target_type, target_id, rationale "
            "FROM focus_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return Focus(*row) if row else None

    def set_focus(
        self, *, current_phase: int, target_type: Optional[str] = None,
        target_id: Optional[int] = None, rationale: Optional[str] = None,
        actor: str = "user",
    ) -> Focus:
        existing = self.get_current()
        self._conn.execute("DELETE FROM focus_state")
        cur = self._conn.execute(
            "INSERT INTO focus_state (current_phase, target_type, target_id, rationale) "
            "VALUES (?, ?, ?, ?)",
            (current_phase, target_type, target_id, rationale),
        )
        _record_status_event(
            self._conn,
            "focus_state",
            cur.lastrowid,
            from_status=(
                f"{existing.target_type}:{existing.target_id}" if existing else None
            ),
            to_status=f"{target_type}:{target_id}",
            reason=rationale,
            actor=actor,
        )
        self._conn.commit()
        return self.get_current()


# ---------------------------------------------------------------------------
# Learning outputs (plan 7.2 #learning_outputs, 12.1 `learn output ...`)
# ---------------------------------------------------------------------------

LEARNING_OUTPUT_TRANSITIONS = {
    # PROPOSED can go straight to SUBMITTED (a user who just does the work
    # and submits a reference, without an explicit "I started this" step,
    # is the common case -- forcing PROPOSED -> ACTIVE -> SUBMITTED for
    # every output would be busywork the plan never asked for) as well as
    # to ACTIVE (the "I'm working on this now" declaration) or ARCHIVED.
    "PROPOSED": {"ACTIVE", "SUBMITTED", "ARCHIVED"},
    "ACTIVE": {"SUBMITTED", "ARCHIVED"},
    # SUBMITTED is terminal except for ARCHIVED -- plan 7.2 gives no
    # "un-submit" or "resubmit" path, and complete() is a one-way door by
    # design (see LearningOutputRepository.complete()).
    "SUBMITTED": {"ARCHIVED"},
    "ARCHIVED": set(),  # terminal, same convention as modules/sources
}


@dataclass
class LearningOutput:
    id: int
    module_id: int
    title: str
    kind: Optional[str]
    phase: Optional[int]
    required: bool
    status: str
    source_file: Optional[str]
    source_line: Optional[int]
    evidence_level: Optional[str]
    reference: Optional[str]


_LEARNING_OUTPUT_COLUMNS = (
    "id, module_id, title, kind, phase, required, status, source_file, "
    "source_line, evidence_level, reference"
)


def _row_to_learning_output(row) -> LearningOutput:
    return LearningOutput(
        id=row[0], module_id=row[1], title=row[2], kind=row[3], phase=row[4],
        required=bool(row[5]), status=row[6], source_file=row[7],
        source_line=row[8], evidence_level=row[9], reference=row[10],
    )


class LearningOutputRepository:
    """The only code that reads/writes learning_outputs.

    Deliberately has no knowledge of sources or concepts: plan 7.2 forbids
    "仅因 source 被 CONSUMED 就自动完成 output", so there must be no code
    path anywhere (including here) that lets a source/concept transition
    reach into this table. The only way an output becomes SUBMITTED is a
    direct, explicit complete() call driven by the user (via `learn output
    complete <output-id> --ref "..."`), never a side effect of anything
    else's state machine.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(
        self,
        *,
        module_id: int,
        title: str,
        kind: Optional[str] = None,
        phase: Optional[int] = None,
        required: bool = False,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
        evidence_level: Optional[str] = None,
    ) -> LearningOutput:
        if evidence_level is not None and evidence_level not in {"PARTIAL", "STRONG"}:
            raise ValueError(f"invalid evidence_level: {evidence_level!r}")
        cur = self._conn.execute(
            "INSERT INTO learning_outputs "
            "(module_id, title, kind, phase, required, source_file, "
            "source_line, evidence_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                module_id, title, kind, phase, int(required), source_file,
                source_line, evidence_level,
            ),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, output_id: int) -> LearningOutput:
        row = self._conn.execute(
            f"SELECT {_LEARNING_OUTPUT_COLUMNS} FROM learning_outputs WHERE id=?",
            (output_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"learning_output {output_id} not found")
        return _row_to_learning_output(row)

    def list_by_module(self, module_id: int) -> list[LearningOutput]:
        rows = self._conn.execute(
            f"SELECT {_LEARNING_OUTPUT_COLUMNS} FROM learning_outputs "
            "WHERE module_id=? ORDER BY id ASC",
            (module_id,),
        ).fetchall()
        return [_row_to_learning_output(row) for row in rows]

    def set_status(
        self, output_id: int, to_status: str, reason: Optional[str] = None,
        actor: str = "user",
    ) -> LearningOutput:
        current = self.get(output_id)
        allowed = LEARNING_OUTPUT_TRANSITIONS.get(current.status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(
                f"learning_output cannot transition from {current.status} "
                f"to {to_status}"
            )
        self._conn.execute(
            "UPDATE learning_outputs SET status=?, updated_at=datetime('now') "
            "WHERE id=?",
            (to_status, output_id),
        )
        _record_status_event(
            self._conn, "learning_output", output_id, current.status,
            to_status, reason, actor,
        )
        self._conn.commit()
        return self.get(output_id)

    def complete(
        self, output_id: int, *, reference: str, actor: str = "user",
    ) -> LearningOutput:
        """The only path that writes `reference` and moves an output to
        SUBMITTED (plan 7.2: "用户完成并提交 reference 后"). Requires a
        non-empty reference -- there is no such thing as a reference-less
        completion in this design, so a blank/whitespace-only string is
        rejected the same as None rather than silently accepted."""
        if reference is None or not reference.strip():
            raise ValueError(
                "complete() requires a non-empty reference "
                "(plan 7.2: output completion means a submitted reference)"
            )
        current = self.get(output_id)
        allowed = LEARNING_OUTPUT_TRANSITIONS.get(current.status, set())
        if "SUBMITTED" not in allowed:
            raise InvalidTransitionError(
                f"learning_output cannot transition from {current.status} "
                "to SUBMITTED"
            )
        self._conn.execute(
            "UPDATE learning_outputs SET status='SUBMITTED', reference=?, "
            "updated_at=datetime('now') WHERE id=?",
            (reference, output_id),
        )
        _record_status_event(
            self._conn, "learning_output", output_id, current.status,
            "SUBMITTED", reason=None, actor=actor,
        )
        self._conn.commit()
        return self.get(output_id)
