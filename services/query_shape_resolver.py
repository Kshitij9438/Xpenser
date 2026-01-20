# services/query_shape_resolver.py

from core.query_shape import QueryShape
from models.query import QueryRequest


def resolve_query_shape(query: QueryRequest) -> QueryShape:
    """
    Determine the authoritative shape of the query result.

    This function MUST be deterministic.
    No heuristics. No language parsing. No LLM.
    """

    # Aggregate without grouping
    if query.aggregate and not query.group_by:
        return QueryShape.AGGREGATE

    # Aggregate with grouping
    if query.aggregate and query.group_by:
        return QueryShape.GROUPED

    # Everything else is a list-style query
    return QueryShape.LIST
