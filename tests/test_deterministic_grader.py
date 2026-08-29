"""TDD for the Level-1 deterministic grader (plan section 9.1).

Covers the four question types the plan calls out as priority:
numeric (with relative/absolute tolerance), unit (Pint-based conversion +
dimension checking), symbolic (SymPy equivalence under stated assumptions),
and discrimination (explicit correct answer + disqualifiers -> MISCONCEPTION).

M2 acceptance also requires at least one boundary test and one error test
for KV cache, parameter memory, and FLOPs -- these use small pure domain
formulas that a real item would reference as its reference_answer.
"""
import pytest

from learning_os.graders.deterministic import (
    grade_discrimination,
    grade_numeric,
    grade_symbolic,
    grade_unit,
    kv_cache_bytes,
    parameter_memory_bytes,
    training_flops,
)


# ---------------------------------------------------------------------------
# Numeric grading
# ---------------------------------------------------------------------------

def test_numeric_within_relative_tolerance_passes():
    assert grade_numeric(answer=101.0, reference=100.0, rel_tol=0.02) == "PASS"


def test_numeric_outside_relative_tolerance_misses():
    assert grade_numeric(answer=110.0, reference=100.0, rel_tol=0.02) == "MISS"


def test_numeric_boundary_exactly_at_tolerance_passes():
    # exactly 2% off with rel_tol=0.02 must be inclusive (PASS), not flaky.
    assert grade_numeric(answer=102.0, reference=100.0, rel_tol=0.02) == "PASS"


def test_numeric_absolute_tolerance_used_for_near_zero_reference():
    # relative tolerance is meaningless near zero; abs_tol must take over.
    assert grade_numeric(answer=0.05, reference=0.0, abs_tol=0.1) == "PASS"
    assert grade_numeric(answer=0.5, reference=0.0, abs_tol=0.1) == "MISS"


def test_numeric_order_of_magnitude_mode():
    assert grade_numeric(answer=1.2e9, reference=1.0e9, order_of_magnitude=True) == "PASS"
    assert grade_numeric(answer=1.2e10, reference=1.0e9, order_of_magnitude=True) == "MISS"


# ---------------------------------------------------------------------------
# Unit grading (Pint)
# ---------------------------------------------------------------------------

def test_unit_grading_accepts_equivalent_units_within_tolerance():
    # 2048 MiB == 2 GiB exactly (binary units); different unit spelling.
    assert grade_unit(answer="2048 MiB", reference="2 GiB", rel_tol=0.01) == "PASS"


def test_unit_grading_rejects_value_outside_tolerance():
    assert grade_unit(answer="3 GiB", reference="2 GiB", rel_tol=0.01) == "MISS"


def test_unit_grading_dimension_mismatch_is_miss_not_crash():
    assert grade_unit(answer="5 seconds", reference="2 GiB", rel_tol=0.01) == "MISS"


def test_unit_grading_unparseable_answer_is_miss_not_crash():
    assert grade_unit(answer="a lot of memory", reference="2 GiB", rel_tol=0.01) == "MISS"


# ---------------------------------------------------------------------------
# Symbolic grading (SymPy)
# ---------------------------------------------------------------------------

def test_symbolic_grading_accepts_algebraically_equivalent_expression():
    assert grade_symbolic(answer="2*(x + y)", reference="2*x + 2*y") == "PASS"


def test_symbolic_grading_rejects_non_equivalent_expression():
    assert grade_symbolic(answer="2*x + y", reference="2*x + 2*y") == "MISS"


def test_symbolic_grading_respects_assumptions():
    # sqrt(x**2) == x only holds for real, non-negative x.
    assert grade_symbolic(
        answer="x", reference="sqrt(x**2)", assumptions={"x": "positive"}
    ) == "PASS"
    assert grade_symbolic(answer="x", reference="sqrt(x**2)") == "MISS"


def test_symbolic_grading_unparseable_answer_is_miss_not_crash():
    assert grade_symbolic(answer="not an expression @@@", reference="2*x") == "MISS"


# ---------------------------------------------------------------------------
# Discrimination grading (correct answer + disqualifiers -> MISCONCEPTION)
# ---------------------------------------------------------------------------

def test_discrimination_correct_choice_passes():
    outcome = grade_discrimination(
        answer="fixed-compute constraint",
        correct="fixed-compute constraint",
        disqualifiers=["bigger model is always optimal"],
    )
    assert outcome == "PASS"


def test_discrimination_disqualifier_choice_is_misconception():
    outcome = grade_discrimination(
        answer="bigger model is always optimal",
        correct="fixed-compute constraint",
        disqualifiers=["bigger model is always optimal", "a fitted ratio is a universal law"],
    )
    assert outcome == "MISCONCEPTION"


def test_discrimination_other_wrong_choice_is_miss():
    outcome = grade_discrimination(
        answer="something unrelated",
        correct="fixed-compute constraint",
        disqualifiers=["bigger model is always optimal"],
    )
    assert outcome == "MISS"


# ---------------------------------------------------------------------------
# Domain formulas: KV cache, parameter memory, FLOPs
# (boundary case + error/edge case each, per M2 acceptance criteria)
# ---------------------------------------------------------------------------

def test_kv_cache_bytes_matches_known_worked_example():
    # 2 (K+V) * num_layers * num_heads * head_dim * seq_len * batch * dtype_bytes
    result = kv_cache_bytes(
        num_layers=32, num_heads=32, head_dim=128, seq_len=2048,
        batch=1, dtype_bytes=2,
    )
    expected = 2 * 32 * 32 * 128 * 2048 * 1 * 2
    assert result == expected


def test_kv_cache_bytes_boundary_seq_len_one():
    result = kv_cache_bytes(
        num_layers=1, num_heads=1, head_dim=1, seq_len=1, batch=1, dtype_bytes=2,
    )
    assert result == 2 * 1 * 1 * 1 * 1 * 1 * 2


def test_kv_cache_bytes_rejects_non_positive_inputs():
    with pytest.raises(ValueError):
        kv_cache_bytes(
            num_layers=0, num_heads=32, head_dim=128, seq_len=2048,
            batch=1, dtype_bytes=2,
        )


def test_parameter_memory_bytes_fp16():
    assert parameter_memory_bytes(num_params=7_000_000_000, bytes_per_param=2) == 14_000_000_000


def test_parameter_memory_bytes_rejects_negative_params():
    with pytest.raises(ValueError):
        parameter_memory_bytes(num_params=-1, bytes_per_param=2)


def test_training_flops_uses_6nd_approximation():
    # Kaplan/Chinchilla approximation: C ~= 6 * N * D
    assert training_flops(num_params=1_000_000_000, num_tokens=300_000_000_000) == (
        6 * 1_000_000_000 * 300_000_000_000
    )


def test_training_flops_rejects_zero_tokens():
    with pytest.raises(ValueError):
        training_flops(num_params=1_000_000_000, num_tokens=0)
