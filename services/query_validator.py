"""
Query Validation Layer (v1.1 — LOCKED)

Purpose:
- Detect hard contradictions between data and answer
- Enforce numeric and structural integrity
- NEVER inspect natural language semantics
- NEVER guess intent

Philosophy:
- Deterministic > clever
- Numbers never lie, words often do
"""

import logging
import re
from typing import Optional, Dict, Any

from models.query import QueryResult, NLPResponse

logger = logging.getLogger("query_validator")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------
class ValidationFailure(Exception):
    """
    Raised when a response contradicts authoritative data.
    """
    pass


# ---------------------------------------------------------------------
# Core Validation
# ---------------------------------------------------------------------
def validate_query_response(
    result: QueryResult,
    response: NLPResponse,
    original_query: str = "",
) -> None:
    """
    Validates that the NLP response does not contradict QueryResult.

    Raises:
        ValidationFailure — if a hard inconsistency is detected
    """

    answer = response.answer.lower()

    # -------------------------------------------------
    # 1. AGGREGATE VALIDATION
    # -------------------------------------------------
    if result.aggregate_result:
        for key, value in result.aggregate_result.items():
            if value is None:
                continue

            # Extract all numbers mentioned in answer
            numbers = _extract_numbers(answer)

            # If no numbers mentioned, let it pass (formatter may be textual)
            if not numbers:
                continue

            # Any mentioned number must match authoritative value
            for n in numbers:
                if not _close_enough(n, value):
                    raise ValidationFailure(
                        f"Aggregate mismatch: expected {value}, found {n}"
                    )

    # -------------------------------------------------
    # 2. ROW COUNT CONSISTENCY
    # -------------------------------------------------
    if result.rows:
        if "no transactions" in answer or "no records" in answer:
            raise ValidationFailure(
                "Answer claims no data, but rows are present"
            )

    # -------------------------------------------------
    # 3. EMPTY RESULT CONSISTENCY
    # -------------------------------------------------
    if not result.rows and not result.aggregate_result:
        if _extract_numbers(answer):
            raise ValidationFailure(
                "Answer mentions numbers but result is empty"
            )

    # If we reached here, response is safe
    return None


# ---------------------------------------------------------------------
# Safe Fallback Construction
# ---------------------------------------------------------------------
def create_safe_fallback_response(
    result: QueryResult,
    user_id: str,
    original_query: str = "",
) -> NLPResponse:
    """
    Deterministic, template-based fallback.
    No LLM involvement.
    """

    # Aggregate fallback
    if result.aggregate_result:
        for key, value in result.aggregate_result.items():
            return NLPResponse(
                user_id=user_id,
                answer=f"{key.capitalize()}: {value}",
                context={
                    "fallback": True,
                    "reason": "validation_failure",
                    "source": "deterministic",
                },
            )

    # Row fallback
    if result.rows:
        return NLPResponse(
            user_id=user_id,
            answer=f"Found {len(result.rows)} matching records.",
            context={
                "fallback": True,
                "reason": "validation_failure",
                "source": "deterministic",
            },
        )

    # Empty fallback
    return NLPResponse(
        user_id=user_id,
        answer="No matching records found.",
        context={
            "fallback": True,
            "reason": "validation_failure",
            "source": "deterministic",
        },
    )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _extract_numbers(text: str) -> list[float]:
    matches = re.findall(r"[₹$]?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", text)
    return [float(m.replace(",", "")) for m in matches]


def _close_enough(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(a - b) <= tol
