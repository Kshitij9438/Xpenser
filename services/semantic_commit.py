# services/semantic_commit.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

from models.query import QueryRequest
from core.query_shape import QueryShape


# ---------------------------------------------------------------------
# Commit Decision Model
# ---------------------------------------------------------------------
class CommitDecisionType(str, Enum):
    EXECUTE = "execute"
    CLARIFY = "clarify"
    REJECT = "reject"


@dataclass(frozen=True)
class CommitDecision:
    type: CommitDecisionType
    reason: Optional[str] = None
    message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------
# Semantic Commit Logic (PURE, DETERMINISTIC)
# ---------------------------------------------------------------------
def semantic_commit(
    query: QueryRequest,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> CommitDecision:
    """
    Decides whether a QueryRequest is SAFE to execute.

    This function is the FINAL AUTHORITY before DB execution.

    Rules:
    - No LLM calls
    - No DB access
    - No inference
    - Deterministic only
    """

    # -------------------------------------------------
    # HARD GUARARDS (should already be true)
    # -------------------------------------------------
    if query.shape is None:
        return CommitDecision(
            type=CommitDecisionType.REJECT,
            reason="missing_query_shape",
        )

    # -------------------------------------------------
    # AGGREGATE SAFETY
    # -------------------------------------------------
    if query.shape is QueryShape.AGGREGATE:
        # Aggregate without date range is ambiguous
        if not query.filters or not query.filters.date_range:
            return CommitDecision(
                type=CommitDecisionType.CLARIFY,
                reason="missing_date_range",
                message=(
                    "Do you want this calculated for a specific time period "
                    "(for example, last month or this year)?"
                ),
            )

    # -------------------------------------------------
    # GROUPED SAFETY
    # -------------------------------------------------
    if query.shape is QueryShape.GROUPED:
        if not query.group_by:
            return CommitDecision(
                type=CommitDecisionType.REJECT,
                reason="grouped_without_group_by",
            )

        # Grouped queries without explicit aggregate are ambiguous
        if not query.aggregate:
            return CommitDecision(
                type=CommitDecisionType.CLARIFY,
                reason="grouped_without_aggregate",
                message=(
                    "Should I group the results by count, sum, or another metric?"
                ),
            )

    # -------------------------------------------------
    # CATEGORY SANITY (optional, context-aware)
    # -------------------------------------------------
    if query.filters and query.filters.category:
        known_categories = (
            context.get("known_categories") if context else None
        )
        if known_categories and query.filters.category not in known_categories:
            return CommitDecision(
                type=CommitDecisionType.CLARIFY,
                reason="unknown_category",
                message=(
                    f"I couldn't find a category named '{query.filters.category}'. "
                    "Could you clarify or choose an existing category?"
                ),
            )

    # -------------------------------------------------
    # LIST QUERIES (SAFE BY DEFAULT)
    # -------------------------------------------------
    if query.shape is QueryShape.LIST:
        return CommitDecision(type=CommitDecisionType.EXECUTE)

    # -------------------------------------------------
    # DEFAULT SAFE PATH
    # -------------------------------------------------
    return CommitDecision(type=CommitDecisionType.EXECUTE)
