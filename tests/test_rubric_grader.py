"""TDD tests for the Level-2 source-grounded rubric grader (plan section 9.2).

Design under test (learning_os.graders.rubric):

- A rubric has `must_understand` atoms (partial credit: PASS if all satisfied,
  PARTIAL if some but not all, MISS if none) and `disqualifiers` (any triggered
  disqualifier overrides the result to MISCONCEPTION, since it indicates a
  fundamentally wrong mental model regardless of how many must_understand
  atoms were otherwise satisfied).
- Manual adjudication is the default, first-class path: a human directly
  states which atoms were satisfied/triggered. This records
  evaluator_kind="manual", human_override=False (there is nothing to
  override -- the human *is* the source of truth).
- LLM-assisted adjudication is an explicit, opt-in adapter. The LLM only
  *proposes* per-atom outcomes with evidence + rationale, and that proposal
  is never itself canonical. A human must either accept it as-is
  (evaluator_kind="llm", human_override=False) or override it
  (evaluator_kind="llm", human_override=True), and either path stores
  model/evaluator_version/generated_at for auditability.
"""
from __future__ import annotations

import pytest

from learning_os.graders.rubric import (
    Adjudication,
    AtomProposal,
    LLMJudgement,
    Rubric,
    accept_llm_judgement,
    adjudicate_manual,
    aggregate_outcome,
    override_llm_judgement,
    propose_llm_adjudication,
)


# ---------------------------------------------------------------------------
# Rubric parsing
# ---------------------------------------------------------------------------

def test_rubric_from_dict_parses_must_understand_and_disqualifiers():
    rubric = Rubric.from_dict(
        {
            "must_understand": [
                "fixed-compute constraint",
                "model/data allocation",
                "empirical fitted relationship",
            ],
            "disqualifiers": [
                "bigger model is always optimal",
                "a fitted ratio is a universal law",
            ],
        }
    )
    assert rubric.must_understand == [
        "fixed-compute constraint",
        "model/data allocation",
        "empirical fitted relationship",
    ]
    assert rubric.disqualifiers == [
        "bigger model is always optimal",
        "a fitted ratio is a universal law",
    ]


def test_rubric_from_dict_defaults_missing_disqualifiers_to_empty_list():
    rubric = Rubric.from_dict({"must_understand": ["a"]})
    assert rubric.must_understand == ["a"]
    assert rubric.disqualifiers == []


def test_rubric_with_no_must_understand_atoms_rejected():
    with pytest.raises(ValueError):
        Rubric.from_dict({"must_understand": [], "disqualifiers": ["x"]})


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

_RUBRIC = Rubric(
    must_understand=["a", "b", "c"],
    disqualifiers=["bad-take"],
)


def test_aggregate_all_must_understand_pass_is_pass():
    outcome = aggregate_outcome(_RUBRIC, understood={"a", "b", "c"}, triggered_disqualifiers=set())
    assert outcome == "PASS"


def test_aggregate_some_but_not_all_pass_is_partial():
    outcome = aggregate_outcome(_RUBRIC, understood={"a"}, triggered_disqualifiers=set())
    assert outcome == "PARTIAL"


def test_aggregate_none_pass_is_miss():
    outcome = aggregate_outcome(_RUBRIC, understood=set(), triggered_disqualifiers=set())
    assert outcome == "MISS"


def test_aggregate_disqualifier_triggered_overrides_everything_to_misconception():
    outcome = aggregate_outcome(
        _RUBRIC, understood={"a", "b", "c"}, triggered_disqualifiers={"bad-take"}
    )
    assert outcome == "MISCONCEPTION"


def test_aggregate_rejects_unknown_atom_names():
    with pytest.raises(ValueError):
        aggregate_outcome(_RUBRIC, understood={"not-a-real-atom"}, triggered_disqualifiers=set())


# ---------------------------------------------------------------------------
# Manual adjudication (default path)
# ---------------------------------------------------------------------------

def test_manual_adjudication_records_evaluator_kind_manual_and_no_override():
    result = adjudicate_manual(
        _RUBRIC, understood=["a", "b", "c"], triggered_disqualifiers=[]
    )
    assert isinstance(result, Adjudication)
    assert result.outcome == "PASS"
    assert result.evaluator_kind == "manual"
    assert result.human_override is False
    assert result.evaluator_version is None


def test_manual_adjudication_partial_credit_and_atom_results_recorded():
    result = adjudicate_manual(_RUBRIC, understood=["a"], triggered_disqualifiers=[])
    assert result.outcome == "PARTIAL"
    assert result.atom_results == {"a": True, "b": False, "c": False, "bad-take": False}


def test_manual_adjudication_misconception_path():
    result = adjudicate_manual(
        _RUBRIC, understood=["a", "b", "c"], triggered_disqualifiers=["bad-take"]
    )
    assert result.outcome == "MISCONCEPTION"
    assert result.atom_results["bad-take"] is True


# ---------------------------------------------------------------------------
# LLM-assisted adjudication (opt-in adapter)
# ---------------------------------------------------------------------------

def _make_proposals(satisfied: set[str], triggered: set[str]) -> list[AtomProposal]:
    proposals = []
    for atom in _RUBRIC.must_understand:
        proposals.append(
            AtomProposal(
                atom=atom,
                kind="must_understand",
                proposed_outcome=atom in satisfied,
                evidence=f"quote about {atom}",
                rationale=f"reasoning about {atom}",
            )
        )
    for atom in _RUBRIC.disqualifiers:
        proposals.append(
            AtomProposal(
                atom=atom,
                kind="disqualifier",
                proposed_outcome=atom in triggered,
                evidence=f"quote about {atom}",
                rationale=f"reasoning about {atom}",
            )
        )
    return proposals


def test_llm_proposal_records_model_version_timestamp_and_evidence():
    proposals = _make_proposals(satisfied={"a", "b"}, triggered=set())
    judgement = propose_llm_adjudication(
        _RUBRIC,
        proposals=proposals,
        model="gpt-x",
        evaluator_version="rubric-eval-v1",
    )
    assert isinstance(judgement, LLMJudgement)
    assert judgement.model == "gpt-x"
    assert judgement.evaluator_version == "rubric-eval-v1"
    assert judgement.generated_at  # non-empty timestamp
    assert judgement.proposals == proposals
    # A bare proposal must never expose a canonical `outcome` -- only an
    # explicit accept/override step produces an Adjudication.
    assert not hasattr(judgement, "outcome")


def test_llm_proposal_missing_atom_coverage_rejected():
    incomplete = _make_proposals(satisfied={"a"}, triggered=set())[:-1]
    with pytest.raises(ValueError):
        propose_llm_adjudication(
            _RUBRIC, proposals=incomplete, model="gpt-x", evaluator_version="v1"
        )


def test_accept_llm_judgement_produces_adjudication_without_human_override():
    proposals = _make_proposals(satisfied={"a", "b", "c"}, triggered=set())
    judgement = propose_llm_adjudication(
        _RUBRIC, proposals=proposals, model="gpt-x", evaluator_version="v1"
    )
    result = accept_llm_judgement(judgement)
    assert result.outcome == "PASS"
    assert result.evaluator_kind == "llm"
    assert result.evaluator_version == "v1"
    assert result.human_override is False


def test_override_llm_judgement_sets_human_override_true_and_uses_user_values():
    # LLM proposes PASS (all satisfied, nothing triggered), but the human
    # disagrees and overrides to reflect only "a" understood plus the
    # disqualifier actually being triggered.
    proposals = _make_proposals(satisfied={"a", "b", "c"}, triggered=set())
    judgement = propose_llm_adjudication(
        _RUBRIC, proposals=proposals, model="gpt-x", evaluator_version="v1"
    )
    result = override_llm_judgement(
        judgement,
        understood=["a"],
        triggered_disqualifiers=["bad-take"],
        rationale="LLM missed that the answer treats the ratio as a universal law",
    )
    assert result.outcome == "MISCONCEPTION"
    assert result.evaluator_kind == "llm"
    assert result.evaluator_version == "v1"
    assert result.human_override is True
    assert "universal law" in result.rationale


def test_llm_judgement_alone_cannot_mutate_canonical_state():
    # propose_llm_adjudication returns an LLMJudgement, not an Adjudication --
    # callers must go through accept/override to get a canonical result.
    proposals = _make_proposals(satisfied={"a", "b", "c"}, triggered=set())
    judgement = propose_llm_adjudication(
        _RUBRIC, proposals=proposals, model="gpt-x", evaluator_version="v1"
    )
    assert not isinstance(judgement, Adjudication)
