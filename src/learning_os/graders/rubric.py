"""Level-2 source-grounded rubric grader (plan section 9.2).

A rubric decomposes an open-ended item into a small set of atomic criteria:

- ``must_understand``: atoms that should each be satisfied for full credit.
  PASS requires all of them; PARTIAL requires at least one but not all;
  MISS requires none.
- ``disqualifiers``: atoms indicating a fundamentally wrong mental model.
  If ANY disqualifier is triggered, the outcome is forced to MISCONCEPTION
  regardless of how many must_understand atoms were otherwise satisfied --
  a technically-correct-sounding answer built on a wrong model is worse
  than an incomplete one.

Manual adjudication is the default, first-class path (plan section 9.2:
"第一版默认人工确认"): a human directly records which atoms were satisfied
or triggered. LLM-assisted adjudication is an explicit opt-in adapter: the
LLM may only *propose* per-atom outcomes with evidence and rationale
(``LLMJudgement``/``AtomProposal``); it can never itself become canonical
truth. A human must explicitly accept or override the proposal to produce
an ``Adjudication`` -- the only object that represents a canonical, storable
result. This mirrors the attempts table columns: evaluator_kind,
evaluator_version, human_override (plan section 7, #attempts).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

Outcome = str  # "PASS" | "PARTIAL" | "MISS" | "MISCONCEPTION"


# ---------------------------------------------------------------------------
# Rubric definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rubric:
    must_understand: list[str] = field(default_factory=list)
    disqualifiers: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Rubric":
        must_understand = list(data.get("must_understand", []))
        disqualifiers = list(data.get("disqualifiers", []))
        if not must_understand:
            raise ValueError("rubric must have at least one must_understand atom")
        return cls(must_understand=must_understand, disqualifiers=disqualifiers)

    def all_atoms(self) -> list[str]:
        return [*self.must_understand, *self.disqualifiers]


# ---------------------------------------------------------------------------
# Aggregation (shared by manual and LLM-derived paths)
# ---------------------------------------------------------------------------

def aggregate_outcome(
    rubric: Rubric, *, understood: set[str], triggered_disqualifiers: set[str]
) -> Outcome:
    known_atoms = set(rubric.all_atoms())
    unknown = (understood | triggered_disqualifiers) - known_atoms
    if unknown:
        raise ValueError(f"unknown rubric atom(s): {sorted(unknown)}")

    if triggered_disqualifiers:
        return "MISCONCEPTION"

    satisfied = [atom for atom in rubric.must_understand if atom in understood]
    if len(satisfied) == len(rubric.must_understand):
        return "PASS"
    if satisfied:
        return "PARTIAL"
    return "MISS"


def _atom_results(
    rubric: Rubric, *, understood: set[str], triggered_disqualifiers: set[str]
) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for atom in rubric.must_understand:
        results[atom] = atom in understood
    for atom in rubric.disqualifiers:
        results[atom] = atom in triggered_disqualifiers
    return results


# ---------------------------------------------------------------------------
# Canonical result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Adjudication:
    outcome: Outcome
    atom_results: dict[str, bool]
    evaluator_kind: str  # "manual" | "llm"
    human_override: bool
    evaluator_version: Optional[str] = None
    model: Optional[str] = None
    rationale: Optional[str] = None


def adjudicate_manual(
    rubric: Rubric, *, understood: list[str], triggered_disqualifiers: list[str]
) -> Adjudication:
    """Default v1 path: a human states which atoms were satisfied/triggered.

    There is nothing to "override" here -- the human's judgement is itself
    the source of truth, so human_override is always False.
    """
    understood_set = set(understood)
    triggered_set = set(triggered_disqualifiers)
    outcome = aggregate_outcome(
        rubric, understood=understood_set, triggered_disqualifiers=triggered_set
    )
    return Adjudication(
        outcome=outcome,
        atom_results=_atom_results(
            rubric, understood=understood_set, triggered_disqualifiers=triggered_set
        ),
        evaluator_kind="manual",
        human_override=False,
        evaluator_version=None,
    )


# ---------------------------------------------------------------------------
# LLM-assisted adjudication (explicit opt-in adapter)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AtomProposal:
    atom: str
    kind: str  # "must_understand" | "disqualifier"
    proposed_outcome: bool  # satisfied (must_understand) / triggered (disqualifier)
    evidence: str
    rationale: str


@dataclass(frozen=True)
class LLMJudgement:
    """A non-canonical proposal. Never mutates state on its own.

    Deliberately has no ``outcome`` attribute: only accept_llm_judgement /
    override_llm_judgement can produce a canonical Adjudication.
    """

    rubric: Rubric
    proposals: list[AtomProposal]
    model: str
    evaluator_version: str
    generated_at: str


def propose_llm_adjudication(
    rubric: Rubric,
    *,
    proposals: list[AtomProposal],
    model: str,
    evaluator_version: str,
) -> LLMJudgement:
    expected_atoms = set(rubric.all_atoms())
    proposed_atoms = {p.atom for p in proposals}
    missing = expected_atoms - proposed_atoms
    if missing:
        raise ValueError(f"LLM proposal missing atom(s): {sorted(missing)}")

    return LLMJudgement(
        rubric=rubric,
        proposals=list(proposals),
        model=model,
        evaluator_version=evaluator_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _proposal_understood_and_triggered(
    judgement: LLMJudgement,
) -> tuple[set[str], set[str]]:
    understood = {
        p.atom
        for p in judgement.proposals
        if p.kind == "must_understand" and p.proposed_outcome
    }
    triggered = {
        p.atom
        for p in judgement.proposals
        if p.kind == "disqualifier" and p.proposed_outcome
    }
    return understood, triggered


def accept_llm_judgement(judgement: LLMJudgement) -> Adjudication:
    """Human reviews the LLM proposal and accepts it as-is."""
    understood, triggered = _proposal_understood_and_triggered(judgement)
    outcome = aggregate_outcome(
        judgement.rubric, understood=understood, triggered_disqualifiers=triggered
    )
    return Adjudication(
        outcome=outcome,
        atom_results=_atom_results(
            judgement.rubric, understood=understood, triggered_disqualifiers=triggered
        ),
        evaluator_kind="llm",
        human_override=False,
        evaluator_version=judgement.evaluator_version,
        model=judgement.model,
    )


def override_llm_judgement(
    judgement: LLMJudgement,
    *,
    understood: list[str],
    triggered_disqualifiers: list[str],
    rationale: Optional[str] = None,
) -> Adjudication:
    """Human disagrees with the LLM proposal and supplies the real result.

    evaluator_kind stays "llm" (an LLM was involved in this attempt's
    workflow) but human_override=True records that the human's atom
    assessment -- not the LLM's -- determined the final outcome.
    """
    understood_set = set(understood)
    triggered_set = set(triggered_disqualifiers)
    outcome = aggregate_outcome(
        judgement.rubric,
        understood=understood_set,
        triggered_disqualifiers=triggered_set,
    )
    return Adjudication(
        outcome=outcome,
        atom_results=_atom_results(
            judgement.rubric,
            understood=understood_set,
            triggered_disqualifiers=triggered_set,
        ),
        evaluator_kind="llm",
        human_override=True,
        evaluator_version=judgement.evaluator_version,
        model=judgement.model,
        rationale=rationale,
    )
