# services/query_shape_resolver.py

from typing import Mapping, Any
from core.query_shape import QueryShape


def resolve_query_shape(draft: Mapping[str, Any]) -> QueryShape:
    """
    Determine the authoritative shape of the query result.

    INPUT: QueryDraft (dict-like)
    OUTPUT: QueryShape

    HARD RULES:
    - Deterministic
    - No LLM
    - No heuristics
    - No mutation
    """

    aggregate = draft.get("aggregate")
    group_by = draft.get("group_by")

    # Aggregate without grouping
    if aggregate and not group_by:
        return QueryShape.AGGREGATE

    # Aggregate with grouping
    if aggregate and group_by:
        return QueryShape.GROUPED

    # Everything else is list-style
    return QueryShape.LIST
