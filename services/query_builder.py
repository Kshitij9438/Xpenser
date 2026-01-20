"""
Query Builder & Data Fetcher (LOCKED)

Responsible for converting QueryRequest into Prisma queries and returning
fully validated QueryResult objects.

Design guarantees:
- Deterministic filtering
- Correct aggregation semantics
- No silent mutation
"""

import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional

from prisma import Prisma
from models.query import QueryRequest, QueryResult, QueryFilters, QueryShape
from services.utils import deep_serialize


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logger = logging.getLogger("query_builder")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_builder.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _parse_iso_date(date_str: str, end_of_day: bool = False) -> datetime:
    dt = datetime.fromisoformat(date_str)
    if end_of_day:
        return dt + timedelta(days=1) - timedelta(microseconds=1)
    return dt


def _to_decimal_list(rows: List[Any], field: str) -> List[Decimal]:
    values: List[Decimal] = []
    for r in rows:
        val = r.get(field) if isinstance(r, dict) else getattr(r, field, None)
        if val is not None:
            values.append(Decimal(str(val)))
    return values


def _compute_aggregate(values: List[Decimal], op: str) -> Optional[float]:
    if op == "count":
        return len(values)
    if not values:
        return None if op in ("min", "max") else 0.0
    if op == "sum":
        return float(sum(values))
    if op == "avg":
        return float(sum(values) / Decimal(len(values)))
    if op == "min":
        return float(min(values))
    if op == "max":
        return float(max(values))
    return None

# ---------------------------------------------------------------------
# WHERE builder
# ---------------------------------------------------------------------
def _build_where(filters: QueryFilters, user_id: str) -> Dict[str, Any]:
    where: Dict[str, Any] = {"user_id": user_id}

    logger.info(f"[WHERE] user_id={user_id}")
    logger.info(f"[WHERE] filters={filters}")

    if filters.category:
        where["category"] = {"equals": filters.category, "mode": "insensitive"}

    if filters.subcategory:
        where["subcategory"] = {"equals": filters.subcategory, "mode": "insensitive"}

    if filters.paymentMethod:
        where["paymentMethod"] = {"equals": filters.paymentMethod, "mode": "insensitive"}

    if filters.companions:
        comps = [c.lower() for c in filters.companions]
        where["companions"] = {"has_some": comps} if len(comps) > 1 else {"has": comps[0]}

    amount_cond: Dict[str, Any] = {}
    if filters.min_amount is not None:
        amount_cond["gte"] = filters.min_amount
    if filters.max_amount is not None:
        amount_cond["lte"] = filters.max_amount
    if amount_cond:
        where["amount"] = amount_cond

    if filters.date_range:
        date_cond: Dict[str, Any] = {}
        if filters.date_range.start:
            date_cond["gte"] = _parse_iso_date(filters.date_range.start)
        if filters.date_range.end:
            date_cond["lte"] = _parse_iso_date(filters.date_range.end, end_of_day=True)
        if date_cond:
            where["date"] = date_cond

    logger.info(f"[WHERE_FINAL] {where}")
    return where

# ---------------------------------------------------------------------
# Core Execution
# ---------------------------------------------------------------------
async def run_query(prisma_db: Prisma, request: QueryRequest) -> QueryResult:
    """
    Execute a QueryRequest safely and deterministically.

    IMPORTANT:
    - QueryBuilder DOES NOT infer intent
    - request.shape MUST be set upstream
    """

    # -------------------------------
    # HARD GUARD: shape is mandatory
    # -------------------------------
    if not hasattr(request, "shape") or request.shape is None:
        raise RuntimeError(
            "QueryRequest.shape is required before execution. "
            "QueryBuilder will not infer intent."
        )

    limit = request.limit if request.limit and request.limit > 0 else 100
    offset = request.offset if request.offset and request.offset >= 0 else 0
    meta = {"limit": limit, "offset": offset}

    where = _build_where(request.filters, request.user_id)

    # -------------------------------------------------
    # AGGREGATE
    # -------------------------------------------------
    if request.shape == QueryShape.AGGREGATE:
        if not request.aggregate:
            raise RuntimeError("AGGREGATE shape requires aggregate field")

        if request.group_by:
            raise RuntimeError("AGGREGATE shape cannot include group_by")

        if request.aggregate == "count":
            total = await prisma_db.expense.count(where=where)
            return QueryResult(
                rows=[],
                aggregate_result={"count": total},
                meta=meta,
            )

        rows = await prisma_db.expense.find_many(where=where)
        values = _to_decimal_list(rows, request.aggregate_field or "amount")
        result = _compute_aggregate(values, request.aggregate)

        return QueryResult(
            rows=[],
            aggregate_result={request.aggregate: result},
            meta=meta,
        )

    # -------------------------------------------------
    # GROUPED
    # -------------------------------------------------
    if request.shape == QueryShape.GROUPED:
        if not request.group_by:
            raise RuntimeError("GROUPED shape requires group_by")

        group_fields = (
            request.group_by if isinstance(request.group_by, list) else [request.group_by]
        )

        if "companions" in group_fields:
            raise RuntimeError("group_by on array field 'companions' is not allowed")

        rows = await prisma_db.expense.find_many(where=where)
        buckets: Dict[Tuple[Any, ...], List[Any]] = {}

        for r in rows:
            key = tuple(getattr(r, f, None) for f in group_fields)
            buckets.setdefault(key, []).append(r)

        results: List[Dict[str, Any]] = []
        for key, items in buckets.items():
            record = {group_fields[i]: deep_serialize(key[i]) for i in range(len(key))}

            if request.aggregate:
                if request.aggregate == "count":
                    record["count"] = len(items)
                else:
                    vals = _to_decimal_list(items, request.aggregate_field or "amount")
                    record[request.aggregate] = _compute_aggregate(vals, request.aggregate)
            else:
                record["count"] = len(items)

            results.append(record)

        if request.sort_by:
            reverse = (request.sort_order or "desc") == "desc"

            def _safe_sort(x):
                v = x.get(request.sort_by)
                if v is None:
                    return (1, None)
                try:
                    return (0, float(v))
                except Exception:
                    return (0, str(v))

            results.sort(key=_safe_sort, reverse=reverse)

        results = results[:limit]

        return QueryResult(rows=results, aggregate_result=None, meta=meta)

    # -------------------------------------------------
    # LIST
    # -------------------------------------------------
    if request.shape == QueryShape.LIST:
        if request.aggregate:
            raise RuntimeError("LIST shape cannot include aggregate")

        find_kwargs: Dict[str, Any] = {
            "where": where,
            "skip": offset,
            "take": limit,
        }

        if request.sort_by:
            find_kwargs["order"] = {request.sort_by: request.sort_order or "desc"}

        rows = await prisma_db.expense.find_many(**find_kwargs)
        total = await prisma_db.expense.count(where=where)

        return QueryResult(
            rows=deep_serialize(rows),
            aggregate_result=None,
            meta={**meta, "total_count": total},
        )

    # -------------------------------------------------
    # UNKNOWN SHAPE
    # -------------------------------------------------
    raise RuntimeError(f"Unknown QueryShape: {request.shape}")
