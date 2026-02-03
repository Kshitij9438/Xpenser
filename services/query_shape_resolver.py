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
    - Semantic intent is authoritative
    """

    semantic = draft.get("semantic_intents", {})

    is_aggregate = semantic.get("aggregate", False)
    is_ranking = semantic.get("ranking", False)

    aggregate = draft.get("aggregate")
    group_by = draft.get("group_by")

    # -----------------------------
    # Aggregate intent
    # -----------------------------
    if is_aggregate:
        if group_by:
            return QueryShape.GROUPED
        return QueryShape.AGGREGATE

    # -----------------------------
    # Ranking intent (still list-shaped)
    # -----------------------------
    if is_ranking:
        return QueryShape.LIST

    # -----------------------------
    # Default: list intent
    # -----------------------------
    return QueryShape.LIST
