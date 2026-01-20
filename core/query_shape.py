# core/query_shape.py

from enum import Enum


class QueryShape(str, Enum):
    """
    The authoritative shape of the answer.

    This defines WHAT KIND of answer the system must produce,
    independent of wording or presentation.
    """

    LIST = "list"            # top-N, recent, ranked rows
    AGGREGATE = "aggregate"  # sum / avg / count / min / max
    GROUPED = "grouped"      # group_by + aggregate
