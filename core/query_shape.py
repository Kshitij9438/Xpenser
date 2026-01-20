# core/query_shape.py
from enum import Enum


class QueryShape(str, Enum):
    """
    The authoritative shape of the answer.
    """

    LIST = "list"
    AGGREGATE = "aggregate"
    GROUPED = "grouped"

    # -----------------------------
    # Semantic helpers (SAFE)
    # -----------------------------
    def is_aggregate(self) -> bool:
        return self in {QueryShape.AGGREGATE, QueryShape.GROUPED}

    def is_grouped(self) -> bool:
        return self is QueryShape.GROUPED

    def is_list(self) -> bool:
        return self is QueryShape.LIST
