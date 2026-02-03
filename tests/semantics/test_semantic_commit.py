import pytest

from services.semantic_commit import (
    semantic_commit,
    CommitDecisionType,
)
from models.query import QueryRequest, QueryFilters, DateRange
from core.query_shape import QueryShape


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def make_query(
    *,
    shape,
    filters=None,
    aggregate=None,
    aggregate_field=None,
    group_by=None,
):
    return QueryRequest(
        user_id="user-123",
        shape=shape,
        filters=filters or QueryFilters(),
        aggregate=aggregate,
        aggregate_field=aggregate_field,
        group_by=group_by,
    )


# ---------------------------------------------------------------------
# TESTS: AGGREGATE SAFETY
# ---------------------------------------------------------------------

def test_aggregate_without_date_range_requires_clarification():
    """
    AGGREGATE queries without a date range are ambiguous
    and must not execute silently.
    """
    query = make_query(
        shape=QueryShape.AGGREGATE,
        aggregate="sum",
        filters=QueryFilters(category="Food"),
    )

    decision = semantic_commit(query)

    assert decision.type == CommitDecisionType.CLARIFY
    assert decision.reason == "missing_date_range"


def test_aggregate_with_date_range_executes():
    """
    AGGREGATE queries with explicit time bounds are safe.
    """
    query = make_query(
        shape=QueryShape.AGGREGATE,
        aggregate="sum",
        filters=QueryFilters(
            category="Food",
            date_range=DateRange(start="2024-01-01", end="2024-01-31"),
        ),
    )

    decision = semantic_commit(query)

    assert decision.type == CommitDecisionType.EXECUTE


# ---------------------------------------------------------------------
# TESTS: GROUPED SAFETY
# ---------------------------------------------------------------------

def test_grouped_without_group_by_is_rejected():
    """
    GROUPED queries without group_by are structurally invalid.
    """
    query = make_query(
        shape=QueryShape.GROUPED,
        aggregate="sum",
    )

    decision = semantic_commit(query)

    assert decision.type == CommitDecisionType.REJECT
    assert decision.reason == "grouped_without_group_by"


def test_grouped_without_aggregate_requires_clarification():
    """
    GROUPED queries without an aggregate are ambiguous.
    """
    query = make_query(
        shape=QueryShape.GROUPED,
        group_by=["category"],
    )

    decision = semantic_commit(query)

    assert decision.type == CommitDecisionType.CLARIFY
    assert decision.reason == "grouped_without_aggregate"


def test_grouped_with_aggregate_executes():
    """
    Fully specified GROUPED queries are safe.
    """
    query = make_query(
        shape=QueryShape.GROUPED,
        group_by=["category"],
        aggregate="sum",
    )

    decision = semantic_commit(query)

    assert decision.type == CommitDecisionType.EXECUTE


# ---------------------------------------------------------------------
# TESTS: LIST SAFETY
# ---------------------------------------------------------------------

def test_list_queries_are_safe_by_default():
    """
    LIST queries are non-destructive and safe.
    """
    query = make_query(
        shape=QueryShape.LIST,
        filters=QueryFilters(category="Food"),
    )

    decision = semantic_commit(query)

    assert decision.type == CommitDecisionType.EXECUTE


# ---------------------------------------------------------------------
# TESTS: CATEGORY SANITY (CONTEXT-AWARE)
# ---------------------------------------------------------------------

def test_unknown_category_requires_clarification():
    """
    Categories not in the user's known categories must be clarified.
    """
    query = make_query(
        shape=QueryShape.LIST,
        filters=QueryFilters(category="Snacks"),
    )

    context = {
        "known_categories": ["Food", "Travel", "Rent"]
    }

    decision = semantic_commit(query, context=context)

    assert decision.type == CommitDecisionType.CLARIFY
    assert decision.reason == "unknown_category"


def test_known_category_executes():
    """
    Known categories are safe.
    """
    query = make_query(
        shape=QueryShape.LIST,
        filters=QueryFilters(category="Food"),
    )

    context = {
        "known_categories": ["Food", "Travel", "Rent"]
    }

    decision = semantic_commit(query, context=context)

    assert decision.type == CommitDecisionType.EXECUTE
