# FILE: services/query_builder.py
"""
Query Builder & Data Fetcher with enhanced logging
"""

import logging
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

from prisma import Prisma
from models.query import QueryRequest, QueryResult, QueryFilters
from services.utils import deep_serialize


logger = logging.getLogger("query_builder")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_builder.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# -----------------------------
# Helper: parse ISO date strings
# -----------------------------
def _parse_iso_date(s: str) -> datetime:
    return datetime.fromisoformat(s)

# -----------------------------
# Helper: build Prisma "where" filter
# -----------------------------
def _build_where_from_filters(filters: QueryFilters, user_id: str) -> Dict[str, Any]:
    """
    Converts QueryFilters -> Prisma-compatible where dictionary.
    Uses case-insensitive string comparison where possible.
    Handles array fields (companions), numeric ranges, and date ranges.
    """
    where: Dict[str, Any] = {"user_id": user_id}
    
    print(f"[QUERY_BUILDER] Building where clause for user_id: {user_id}")
    print(f"[QUERY_BUILDER] Filters: {filters}")

    # -------- String fields: use Prisma "mode: insensitive" --------
    if getattr(filters, "category", None):
        where["category"] = {"equals": filters.category, "mode": "insensitive"}
        print(f"[QUERY_BUILDER] Added category filter: {filters.category}")
    if getattr(filters, "subcategory", None):
        where["subcategory"] = {"equals": filters.subcategory, "mode": "insensitive"}
        print(f"[QUERY_BUILDER] Added subcategory filter: {filters.subcategory}")
    if getattr(filters, "paymentMethod", None):
        where["paymentMethod"] = {"equals": filters.paymentMethod, "mode": "insensitive"}
        print(f"[QUERY_BUILDER] Added payment method filter: {filters.paymentMethod}")

    # -------- Array field: companions --------
    companions = getattr(filters, "companions", None)
    if companions:
        # Prisma cannot do case-insensitive 'has'/'has_some' yet, so normalize to lowercase
        if isinstance(companions, list):
            lc_companions = [c.lower() for c in companions]
            where["companions"] = {"has_some": lc_companions} if len(lc_companions) > 1 else {"has": lc_companions[0]}
        else:
            where["companions"] = {"has": companions.lower()}
        print(f"[QUERY_BUILDER] Added companions filter: {companions}")

    # -------- Numeric filters: amount --------
    amt_filter: Dict[str, Any] = {}
    if getattr(filters, "min_amount", None) is not None:
        amt_filter["gte"] = filters.min_amount
        print(f"[QUERY_BUILDER] Added min_amount filter: {filters.min_amount}")
    if getattr(filters, "max_amount", None) is not None:
        amt_filter["lte"] = filters.max_amount
        print(f"[QUERY_BUILDER] Added max_amount filter: {filters.max_amount}")
    if amt_filter:
        where["amount"] = amt_filter

    # -------- Date range filters --------
    dr = getattr(filters, "date_range", None)
    if dr:
        print(f"[QUERY_BUILDER] Processing date range: {dr}")
        date_cond: Dict[str, Any] = {}
        if getattr(dr, "start", None):
            start_date = _parse_iso_date(dr.start)
            date_cond["gte"] = start_date
            print(f"[QUERY_BUILDER] Added start date filter: {start_date}")
        if getattr(dr, "end", None):
            end_date = _parse_iso_date(dr.end)
            date_cond["lte"] = end_date
            print(f"[QUERY_BUILDER] Added end date filter: {end_date}")
        if date_cond:
            where["date"] = date_cond
            print(f"[QUERY_BUILDER] Final date condition: {date_cond}")

    print(f"[QUERY_BUILDER] Final where clause: {where}")
    return where
# -----------------------------
# Helper: extract Decimal list
# -----------------------------
def _to_decimal_list(rows: List[Any], attr: str = "amount") -> List[Decimal]:
    vals: List[Decimal] = []
    for r in rows:
        v = None
        if isinstance(r, dict):
            v = r.get(attr)
        else:
            v = getattr(r, attr, None)
            if v is None and hasattr(r, "__dict__"):
                v = r.__dict__.get(attr)
        if v is None:
            continue
        vals.append(Decimal(str(v)))
    return vals

# -----------------------------
# Helper: compute aggregate
# -----------------------------
def _compute_aggregate(decimals: List[Decimal], op: str) -> Optional[float]:
    if op == "count":
        return len(decimals)
    if not decimals:
        return None if op in ("min", "max") else 0.0
    if op == "sum":
        return float(sum(decimals))
    if op == "avg":
        return float(sum(decimals) / Decimal(len(decimals)))
    if op == "min":
        return float(min(decimals))
    if op == "max":
        return float(max(decimals))
    return None

# -----------------------------
# Core: run query
# -----------------------------
async def run_query(prisma_db: Prisma, request: QueryRequest) -> QueryResult:
    """
    Accepts QueryRequest, executes Prisma query, handles aggregation/group_by,
    returns QueryResult.
    """
    # Safety defaults
    if not request.limit or request.limit <= 0:
        request.limit = 100
    if not request.offset or request.offset < 0:
        request.offset = 0

    where = _build_where_from_filters(request.filters, request.user_id)
    meta = {"limit": request.limit, "offset": request.offset}

    # -------- Aggregation-only (no group_by) --------
    if request.aggregate and not request.group_by:
        if request.aggregate == "count":
            total = await prisma_db.expense.count(where=where)
            return QueryResult(rows=[], aggregate_result={"count": total}, meta=meta)

        rows = await prisma_db.expense.find_many(where=where)
        decimals = _to_decimal_list(rows, request.aggregate_field or "amount")
        agg_val = _compute_aggregate(decimals, request.aggregate)
        return QueryResult(rows=[], aggregate_result={request.aggregate: agg_val}, meta=meta)

    # -------- Group-by (Python-side) --------
    if request.group_by:
        group_fields: List[str] = request.group_by if isinstance(request.group_by, list) else [request.group_by]

        # forbid array fields
        for gf in group_fields:
            if gf == "companions":
                raise ValueError("Cannot group_by array field 'companions'")

        rows = await prisma_db.expense.find_many(where=where)
        groups: Dict[Tuple[Any, ...], List[Any]] = {}

        for r in rows:
            key = tuple(getattr(r, f, None) if not isinstance(r, dict) else r.get(f) for f in group_fields)
            groups.setdefault(key, []).append(r)

        results: List[Dict[str, Any]] = []
        for key, items in groups.items():
            g: Dict[str, Any] = {group_fields[i]: deep_serialize(key[i]) for i in range(len(group_fields))}
            if request.aggregate:
                if request.aggregate == "count":
                    g["count"] = len(items)
                else:
                    decimals = _to_decimal_list(items, request.aggregate_field or "amount")
                    g[request.aggregate] = _compute_aggregate(decimals, request.aggregate)
            else:
                g["count"] = len(items)
            results.append(g)

        # optional sorting on grouped results
        if request.sort_by:
            sort_key = request.sort_by
            reverse = (request.sort_order or "desc") == "desc"
            def _grp_sort_key(item: Dict[str, Any]):
                val = item.get(sort_key)
                if val is None:
                    return (1, None)
                try:
                    return (0, float(val))
                except Exception:
                    return (0, str(val))
            results.sort(key=_grp_sort_key, reverse=reverse)

        if request.limit:
            results = results[:request.limit]

        return QueryResult(rows=results, aggregate_result=None, meta=meta)

    # -------- Normal find (no group, no aggregate) --------
    find_kwargs: Dict[str, Any] = {"where": where, "skip": request.offset, "take": request.limit}
    if request.sort_by:
        find_kwargs["order"] = {request.sort_by: request.sort_order or "desc"}

    rows_raw = await prisma_db.expense.find_many(**find_kwargs)
    total_count = await prisma_db.expense.count(where=where)

    return QueryResult(
        rows=deep_serialize(rows_raw),
        aggregate_result=None,
        meta={**meta, "total_count": total_count},
    )
