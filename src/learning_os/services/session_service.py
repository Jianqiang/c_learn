"""Session & attempt service (plan section 8 table, section 14 M0 acceptance).

Two durability guarantees this module exists to provide:

1. "一次命令能继续 session" -- start_or_resume() looks for an existing OPEN
   session with the same (session_type, target_type, target_id) before
   creating a new one, so re-invoking a CLI command (e.g. after the process
   was killed) continues the same session instead of forking a duplicate.

2. "中断后不丢 attempt" -- start_attempt() writes the attempt row to SQLite
   *before* the user has answered anything (outcome/submitted_at are NULL).
   If the process dies mid-attempt, the row still exists and can be resumed
   or at least audited; submit_attempt() only ever fills in an existing row,
   it never risks losing an attempt that was already in flight.

record_attempt() is a convenience one-shot wrapper around
start_attempt()+submit_attempt() for callers (e.g. deterministic drills)
that have the full outcome ready immediately and don't need the two-phase
durability window.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

VALID_SESSION_TYPES = {"drill", "learn", "recall", "review", "apply"}
VALID_OUTCOMES = {"PASS", "PARTIAL", "MISS", "MISCONCEPTION", "SKIPPED"}


@dataclass
class Session:
    id: int
    session_type: str
    target_type: Optional[str]
    target_id: Optional[int]
    started_at: str
    ended_at: Optional[str]
    time_budget_seconds: Optional[int]
    item_limit: Optional[int]
    status: str
    user_goal: Optional[str]
    user_output: Optional[str]


@dataclass
class Attempt:
    id: int
    session_id: int
    item_id: int
    started_at: str
    submitted_at: Optional[str]
    answer: Optional[str]
    outcome: Optional[str]
    confidence: Optional[float]
    latency_seconds: Optional[float]
    misconception_code: Optional[str]
    feedback: Optional[str]
    evaluator_kind: Optional[str]
    evaluator_version: Optional[str]
    human_override: bool


_SESSION_COLUMNS = (
    "id, session_type, target_type, target_id, started_at, ended_at, "
    "time_budget_seconds, item_limit, status, user_goal, user_output"
)
_ATTEMPT_COLUMNS = (
    "id, session_id, item_id, started_at, submitted_at, answer, outcome, "
    "confidence, latency_seconds, misconception_code, feedback, "
    "evaluator_kind, evaluator_version, human_override"
)


def _row_to_session(row) -> Session:
    return Session(
        id=row[0], session_type=row[1], target_type=row[2], target_id=row[3],
        started_at=row[4], ended_at=row[5], time_budget_seconds=row[6],
        item_limit=row[7], status=row[8], user_goal=row[9], user_output=row[10],
    )


def _row_to_attempt(row) -> Attempt:
    return Attempt(
        id=row[0], session_id=row[1], item_id=row[2], started_at=row[3],
        submitted_at=row[4], answer=row[5], outcome=row[6], confidence=row[7],
        latency_seconds=row[8], misconception_code=row[9], feedback=row[10],
        evaluator_kind=row[11], evaluator_version=row[12],
        human_override=bool(row[13]),
    )


class SessionService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # -- sessions ----------------------------------------------------------

    def start_or_resume(
        self,
        *,
        session_type: str,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        time_budget_seconds: Optional[int] = None,
        item_limit: Optional[int] = None,
        user_goal: Optional[str] = None,
    ) -> Session:
        if session_type not in VALID_SESSION_TYPES:
            raise ValueError(f"invalid session_type: {session_type!r}")

        existing = self._conn.execute(
            f"SELECT {_SESSION_COLUMNS} FROM sessions "
            "WHERE session_type=? AND target_type IS ? AND target_id IS ? "
            "AND status='OPEN' ORDER BY id DESC LIMIT 1",
            (session_type, target_type, target_id),
        ).fetchone()
        if existing is not None:
            return _row_to_session(existing)

        cur = self._conn.execute(
            "INSERT INTO sessions "
            "(session_type, target_type, target_id, time_budget_seconds, "
            "item_limit, user_goal) VALUES (?, ?, ?, ?, ?, ?)",
            (session_type, target_type, target_id, time_budget_seconds,
             item_limit, user_goal),
        )
        self._conn.commit()
        return self.get_session(cur.lastrowid)

    def get_session(self, session_id: int) -> Session:
        row = self._conn.execute(
            f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"session {session_id} not found")
        return _row_to_session(row)

    def end(self, session_id: int, *, user_output: Optional[str] = None) -> Session:
        session = self.get_session(session_id)
        if session.status != "OPEN":
            raise ValueError(f"session {session_id} is already {session.status}")
        self._conn.execute(
            "UPDATE sessions SET status='ENDED', ended_at=datetime('now'), "
            "user_output=COALESCE(?, user_output) WHERE id=?",
            (user_output, session_id),
        )
        self._conn.commit()
        return self.get_session(session_id)

    # -- attempts ------------------------------------------------------------

    def start_attempt(self, session_id: int, item_id: int) -> Attempt:
        session = self.get_session(session_id)
        if session.status != "OPEN":
            raise ValueError(
                f"cannot start an attempt on a {session.status} session"
            )
        cur = self._conn.execute(
            "INSERT INTO attempts (session_id, item_id) VALUES (?, ?)",
            (session_id, item_id),
        )
        self._conn.commit()
        return self.get_attempt(cur.lastrowid)

    def get_attempt(self, attempt_id: int) -> Attempt:
        row = self._conn.execute(
            f"SELECT {_ATTEMPT_COLUMNS} FROM attempts WHERE id=?", (attempt_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"attempt {attempt_id} not found")
        return _row_to_attempt(row)

    def submit_attempt(
        self,
        attempt_id: int,
        *,
        answer: Optional[str] = None,
        outcome: str,
        confidence: Optional[float] = None,
        latency_seconds: Optional[float] = None,
        misconception_code: Optional[str] = None,
        feedback: Optional[str] = None,
        evaluator_kind: Optional[str] = None,
        evaluator_version: Optional[str] = None,
        human_override: bool = False,
    ) -> Attempt:
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"invalid outcome: {outcome!r}")
        self.get_attempt(attempt_id)  # raises KeyError if missing
        self._conn.execute(
            "UPDATE attempts SET submitted_at=datetime('now'), answer=?, "
            "outcome=?, confidence=?, latency_seconds=?, misconception_code=?, "
            "feedback=?, evaluator_kind=?, evaluator_version=?, human_override=? "
            "WHERE id=?",
            (
                answer, outcome, confidence, latency_seconds, misconception_code,
                feedback, evaluator_kind, evaluator_version, int(human_override),
                attempt_id,
            ),
        )
        self._conn.commit()
        return self.get_attempt(attempt_id)

    def record_attempt(
        self,
        session_id: int,
        item_id: int,
        *,
        answer: Optional[str] = None,
        outcome: str,
        confidence: Optional[float] = None,
        latency_seconds: Optional[float] = None,
        misconception_code: Optional[str] = None,
        feedback: Optional[str] = None,
        evaluator_kind: Optional[str] = None,
        evaluator_version: Optional[str] = None,
        human_override: bool = False,
    ) -> Attempt:
        """One-shot start_attempt() + submit_attempt() for callers that
        already have the full outcome (e.g. a deterministic grader result).
        """
        attempt = self.start_attempt(session_id, item_id)
        return self.submit_attempt(
            attempt.id,
            answer=answer,
            outcome=outcome,
            confidence=confidence,
            latency_seconds=latency_seconds,
            misconception_code=misconception_code,
            feedback=feedback,
            evaluator_kind=evaluator_kind,
            evaluator_version=evaluator_version,
            human_override=human_override,
        )

    def list_attempts(self, session_id: int) -> list[Attempt]:
        rows = self._conn.execute(
            f"SELECT {_ATTEMPT_COLUMNS} FROM attempts "
            "WHERE session_id=? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [_row_to_attempt(row) for row in rows]
