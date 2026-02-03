# services/query_semantic_validator.py

from fastapi import HTTPException


def validate_query_semantics(draft):
    """
    Enforces strict semantic invariants on QueryDraft.
    MUST run before shape resolution.
    MUST NOT mutate the draft.
    """

    # Support dict or model
    aggregate = draft.get("aggregate") if isinstance(draft, dict) else draft.aggregate
    group_by = draft.get("group_by") if isinstance(draft, dict) else draft.group_by
    columns = draft.get("columns") if isinstance(draft, dict) else draft.columns
    semantic_intents = draft.get("semantic_intents", {}) if isinstance(draft, dict) else {}

    intents = []

    if semantic_intents.get("list"):
        intents.append("list")

    if semantic_intents.get("aggregate"):
        intents.append("aggregate")

    # -------- Invariant 1 --------
    # Cannot mix list + aggregate semantics
    if len(intents) > 1:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_QUERY_SHAPE",
                    "message": "Query contains multiple semantic intents",
                    "details": {"intents": intents},
                }
            },
        )

    # -------- Invariant 2 --------
    # Grouping semantics REQUIRE aggregate
    if semantic_intents.get("grouping") and aggregate is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_QUERY_SHAPE",
                    "message": "group_by requires aggregate",
                }
            },
        )

    # -------- Invariant 3 --------
    # Aggregate queries cannot specify explicit columns
    if aggregate is not None and columns is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_QUERY_SHAPE",
                    "message": "Aggregate queries cannot specify columns",
                }
            },
        )
