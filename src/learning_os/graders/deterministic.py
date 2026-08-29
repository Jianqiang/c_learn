"""Level-1 deterministic grader (plan section 9.1).

Every function here returns a plain outcome string from
{"PASS", "PARTIAL", "MISS", "MISCONCEPTION"} (grade_discrimination can return
MISCONCEPTION; the numeric/unit/symbolic graders only return PASS/MISS since
there is no partial credit concept for a single deterministic check).

Design choices:
- Never raise on malformed *answers* -- a garbled answer is graded MISS, not
  a crash, because attempts come from real users typing free text.
- Domain formulas (kv_cache_bytes, parameter_memory_bytes, training_flops)
  validate their *inputs* strictly (raise ValueError) because those are
  called by our own item authoring/reference-answer code, not by user input.
"""
from __future__ import annotations

import math
from typing import Optional

import pint
import sympy
from sympy.parsing.sympy_parser import parse_expr

_UREG = pint.UnitRegistry()

Outcome = str  # "PASS" | "PARTIAL" | "MISS" | "MISCONCEPTION"


# ---------------------------------------------------------------------------
# Numeric
# ---------------------------------------------------------------------------

def grade_numeric(
    *,
    answer: float,
    reference: float,
    rel_tol: Optional[float] = None,
    abs_tol: Optional[float] = None,
    order_of_magnitude: bool = False,
) -> Outcome:
    if order_of_magnitude:
        if answer <= 0 or reference <= 0:
            return "MISS"
        return "PASS" if math.floor(math.log10(answer)) == math.floor(math.log10(reference)) else "MISS"

    if abs_tol is not None and abs(reference) < 1e-12:
        return "PASS" if abs(answer - reference) <= abs_tol else "MISS"

    tol = rel_tol if rel_tol is not None else 0.0
    allowed = abs(reference) * tol
    if abs_tol is not None:
        allowed = max(allowed, abs_tol)
    return "PASS" if abs(answer - reference) <= allowed else "MISS"


# ---------------------------------------------------------------------------
# Unit (Pint)
# ---------------------------------------------------------------------------

def grade_unit(*, answer: str, reference: str, rel_tol: float = 0.0) -> Outcome:
    try:
        answer_q = _UREG.parse_expression(answer)
        reference_q = _UREG.parse_expression(reference)
    except Exception:
        return "MISS"

    try:
        answer_in_ref_units = answer_q.to(reference_q.units)
    except pint.DimensionalityError:
        return "MISS"
    except Exception:
        return "MISS"

    a = answer_in_ref_units.magnitude
    r = reference_q.magnitude
    allowed = abs(r) * rel_tol
    return "PASS" if abs(a - r) <= allowed else "MISS"


# ---------------------------------------------------------------------------
# Symbolic (SymPy)
# ---------------------------------------------------------------------------

def grade_symbolic(
    *, answer: str, reference: str, assumptions: Optional[dict[str, str]] = None,
) -> Outcome:
    assumptions = assumptions or {}
    local_symbols = {
        name: sympy.Symbol(name, **{value: True})
        for name, value in assumptions.items()
    }
    try:
        answer_expr = parse_expr(answer, local_dict=local_symbols)
        reference_expr = parse_expr(reference, local_dict=local_symbols)
    except Exception:
        return "MISS"

    try:
        diff = sympy.simplify(answer_expr - reference_expr)
    except Exception:
        return "MISS"

    return "PASS" if diff == 0 else "MISS"


# ---------------------------------------------------------------------------
# Discrimination
# ---------------------------------------------------------------------------

def grade_discrimination(
    *, answer: str, correct: str, disqualifiers: Optional[list[str]] = None,
) -> Outcome:
    disqualifiers = disqualifiers or []
    normalized_answer = answer.strip().lower()
    if normalized_answer == correct.strip().lower():
        return "PASS"
    if normalized_answer in {d.strip().lower() for d in disqualifiers}:
        return "MISCONCEPTION"
    return "MISS"


# ---------------------------------------------------------------------------
# Domain formulas used as reference_answer generators for LLM-systems items
# ---------------------------------------------------------------------------

def kv_cache_bytes(
    *, num_layers: int, num_heads: int, head_dim: int, seq_len: int,
    batch: int, dtype_bytes: int,
) -> int:
    for name, value in {
        "num_layers": num_layers, "num_heads": num_heads, "head_dim": head_dim,
        "seq_len": seq_len, "batch": batch, "dtype_bytes": dtype_bytes,
    }.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")
    return 2 * num_layers * num_heads * head_dim * seq_len * batch * dtype_bytes


def parameter_memory_bytes(*, num_params: int, bytes_per_param: int) -> int:
    if num_params < 0:
        raise ValueError(f"num_params must be non-negative, got {num_params}")
    if bytes_per_param <= 0:
        raise ValueError(f"bytes_per_param must be positive, got {bytes_per_param}")
    return num_params * bytes_per_param


def training_flops(*, num_params: int, num_tokens: int) -> int:
    if num_params <= 0:
        raise ValueError(f"num_params must be positive, got {num_params}")
    if num_tokens <= 0:
        raise ValueError(f"num_tokens must be positive, got {num_tokens}")
    return 6 * num_params * num_tokens
