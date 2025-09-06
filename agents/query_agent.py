# FILE: agents/query_agent.py
"""
Updated Query Agent (Prisma Python compatible)
- Implements Python-side aggregation/group_by because prisma-client-py lacks aggregate/group_by.
- Adds a robust deep serializer that converts Decimal/datetime/pydantic models to JSON-safe primitives.
- Fixes previous kwargs misuse (select/positional args) and other edge cases.
- Defensive parser/result handling for pydantic_ai Agent outputs.

See the other files in this document: models/query.py and services/query_parser.py
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple, Optional

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from prisma import Prisma

from models.query import QueryRequest, QueryResult, NLPResponse
from config import GOOGLE_API_KEY

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("query_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_audit.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

# -----------------------------
# Prisma Client
# -----------------------------
prisma_db = Prisma()  # app.py should connect this instance at startup

# -----------------------------
# LLM Provider / Model
# -----------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel("gemini-1.5-flash", provider=provider)

# -----------------------------
# Query Parsing Agent (converts NL -> QueryRequest)
# -----------------------------
query_parser_agent = Agent(
    model=model,
    system_prompt="""
You are a Query Parser Agent. Convert user natural language into a JSON object
that matches the QueryRequest schema.

Rules:
- Always include "user_id".
- Only use these filters: category, subcategory, companions, paymentMethod, min_amount, max_amount, date_range.start, date_range.end
- Aggregation only if explicitly requested: "sum", "avg", "count", "min", "max"
- Default aggregate_field is "amount" unless user specifies otherwise.
- Group_by allowed only on safe scalar fields (no arrays like companions).
- Output strictly JSON, no explanations, no text outside JSON.

Examples:

User: "How much did I spend last month?" (user_id=123)
Output:
{
  "user_id": "123",
  "filters": {
    "date_range": {"start": "2025-08-01", "end": "2025-08-31"}
  },
  "aggregate": "sum",
  "aggregate_field": "amount",
  "group_by": null,
  "limit": 100,
  "offset": 0,
  "sort_by": "date",
  "sort_order": "desc"
}

User: "Show all my food expenses with Alice" (user_id=123)
Output:
{
  "user_id": "123",
  "filters": {
    "category": "Food",
    "companions": ["Alice"]
  },
  "aggregate": null,
  "aggregate_field": "amount",
  "group_by": null,
  "limit": 100,
  "offset": 0,
  "sort_by": "date",
  "sort_order": "desc"
}
""",
    output_type=QueryRequest,
)

# -----------------------------
# Query Answer Agent (converts DB result -> friendly NLPResponse)
# -----------------------------
query_answer_agent = Agent(
    model=model,
    system_prompt="""
You are a Query Answer Agent.
Input: user_query, db_result, user_id
Output: friendly NLPResponse.answer and optional structured context.

Be concise, professional, and honest about uncertainty.

Your output must strictly follow this JSON schema:
{
  "user_id": "<same user_id provided in input>",
  "answer": "<natural language summary of db_result>",
  "context": { ... any structured info ... },
  "query": null,
  "output": null
}

Examples:
Input: {"user_query": "How much did I spend last month?", "db_result": {"aggregate_result": {"sum": 1200}}, "user_id": "22f8e821"}
Output: {"user_id": "22f8e821", "answer": "You spent ₹1,200 last month.", "context": {"sum": 1200}, "query": null, "output": null}

Input: {"user_query": "Show my food expenses", "db_result": {"rows": [{"category": "Food", "amount": 200}]} , "user_id": "22f8e821"}
Output: {"user_id": "22f8e821", "answer": "You had 1 food expense of ₹200.", "context": {"rows": 1}, "query": null, "output": null}
""",
    output_type=NLPResponse,
)


# -----------------------------
# Helpers
# -----------------------------

def _deep_serialize(obj: Any) -> Any:
    """
    Recursively convert objects to JSON-safe primitives.
    - Decimal -> float (or str if you want exact cents)
    - datetime -> ISO string
    - pydantic models (model_dump / dict) -> dict
    - lists/tuples/sets/dicts -> recursively processed
    """
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        # Using float for ease of frontend use. Change to str(obj) to preserve exact precision.
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    # pydantic v2 models
    if hasattr(obj, "model_dump"):
        try:
            return _deep_serialize(obj.model_dump())
        except Exception:
            pass
    # pydantic v1 or other objects
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return _deep_serialize(obj.dict())
        except Exception:
            pass
    if isinstance(obj, dict):
        return {k: _deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_deep_serialize(v) for v in obj]
    # fallback for simple primitives
    if isinstance(obj, (str, int, float, bool)):
        return obj
    # last-resort: attempt attribute access
    try:
        return _deep_serialize(obj.__dict__)
    except Exception:
        return str(obj)


def _parse_iso_date(s: str) -> datetime:
    # Accept ISO date/time strings; let ValueError bubble up to be handled by caller
    return datetime.fromisoformat(s)


def _build_where_from_filters(filters: Any, user_id: Any) -> Dict[str, Any]:
    where: Dict[str, Any] = {"user_id": user_id}

    if getattr(filters, "category", None):
        where["category"] = filters.category
    if getattr(filters, "subcategory", None):
        where["subcategory"] = filters.subcategory

    companions = getattr(filters, "companions", None)
    if companions:
        if isinstance(companions, list):
            # Prisma Python supports `has` and `has_some` for string[]
            where["companions"] = {"has_some": companions} if len(companions) > 1 else {"has": companions[0]}
        else:
            where["companions"] = {"has": companions}

    if getattr(filters, "paymentMethod", None):
        where["paymentMethod"] = filters.paymentMethod

    amt_filter: Dict[str, Any] = {}
    if getattr(filters, "min_amount", None) is not None:
        amt_filter["gte"] = filters.min_amount
    if getattr(filters, "max_amount", None) is not None:
        amt_filter["lte"] = filters.max_amount
    if amt_filter:
        where["amount"] = amt_filter

    dr = getattr(filters, "date_range", None)
    if dr:
        date_cond: Dict[str, Any] = {}
        if getattr(dr, "start", None):
            date_cond["gte"] = _parse_iso_date(dr.start)
        if getattr(dr, "end", None):
            date_cond["lte"] = _parse_iso_date(dr.end)
        if date_cond:
            where["date"] = date_cond

    return where


# Aggregation helpers
def _to_decimal_list(rows: List[Any], attr: str = "amount") -> List[Decimal]:
    vals: List[Decimal] = []
    for r in rows:
        v = None
        # row might be a pydantic model, an object, or a dict
        if isinstance(r, dict):
            v = r.get(attr)
        else:
            v = getattr(r, attr, None)
            if v is None and hasattr(r, "__dict__"):
                v = r.__dict__.get(attr)
        if v is None:
            continue
        if isinstance(v, Decimal):
            vals.append(v)
        else:
            try:
                vals.append(Decimal(str(v)))
            except Exception:
                continue
    return vals


def _compute_aggregate(decimals: List[Decimal], op: str) -> Optional[float]:
    if op == "count":
        return len(decimals)
    if not decimals:
        return None if op in ("min", "max") else 0.0

    if op == "sum":
        total = sum(decimals, Decimal("0"))
        return float(total)
    if op == "avg":
        total = sum(decimals, Decimal("0"))
        avg = total / Decimal(len(decimals))
        return float(avg)
    if op == "min":
        return float(min(decimals))
    if op == "max":
        return float(max(decimals))
    return None


# -----------------------------
# Run Query (Prisma Python compatible)
# -----------------------------
async def run_query(request: QueryRequest) -> QueryResult:
    # Safety defaults
    if request.limit is None or request.limit <= 0:
        request.limit = 100
    if request.offset is None or request.offset < 0:
        request.offset = 0

    where = _build_where_from_filters(request.filters, request.user_id)
    meta = {"limit": request.limit, "offset": request.offset}

    # Aggregation-only (no grouping)
    if request.aggregate and not request.group_by:
        # count can be done in DB efficiently
        if request.aggregate == "count":
            total = await prisma_db.expense.count(where=where)
            return QueryResult(rows=[], aggregate_result={"count": total}, meta=meta)

        # numeric aggregates: fetch values and compute in Python
        rows = await prisma_db.expense.find_many(where=where)
        decimals = _to_decimal_list(rows, request.aggregate_field or "amount")
        agg_val = _compute_aggregate(decimals, request.aggregate)
        return QueryResult(rows=[], aggregate_result={request.aggregate: agg_val}, meta=meta)

    # Group-by (Python-side)
    if request.group_by:
        group_fields: List[str] = request.group_by if isinstance(request.group_by, list) else [request.group_by]

        # forbid array fields
        array_fields = {"companions"}
        for gf in group_fields:
            if gf in array_fields:
                raise ValueError(f"Cannot group_by array field: {gf}")

        rows = await prisma_db.expense.find_many(where=where)

        groups: Dict[Tuple[Any, ...], List[Any]] = {}
        for r in rows:
            key = tuple(getattr(r, f, None) if not isinstance(r, dict) else r.get(f) for f in group_fields)
            groups.setdefault(key, []).append(r)

        results: List[Dict[str, Any]] = []
        for key, items in groups.items():
            g: Dict[str, Any] = {group_fields[i]: _deep_serialize(key[i]) for i in range(len(group_fields))}
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
            results = results[: request.limit]

        return QueryResult(rows=results, aggregate_result=None, meta=meta)

    # Normal find
    find_kwargs: Dict[str, Any] = {"where": where, "skip": request.offset or 0, "take": request.limit}
    if request.sort_by:
        find_kwargs["order"] = {request.sort_by: request.sort_order or "desc"}

    rows_raw = await prisma_db.expense.find_many(**find_kwargs)
    total_count = await prisma_db.expense.count(where=where)

    return QueryResult(
        rows=_deep_serialize(rows_raw),
        aggregate_result=None,
        meta={**meta, "total_count": total_count},
    )


# -----------------------------
# Full Query Handling
# -----------------------------
async def handle_query(user_input: str, user_id: Any) -> NLPResponse:
    # 1) Parse user query -> QueryRequest
    try:
        parsed = await query_parser_agent.run(f"User (id={user_id}) asked: {user_input}")
        if not getattr(parsed, "output", None):
            raise ValueError(f"Parser returned no output: {_deep_serialize(parsed)}")

        # parsed.output should be a QueryRequest (or a dict matching it)
        if isinstance(parsed.output, QueryRequest):
            query_request = parsed.output
        elif isinstance(parsed.output, dict):
            query_request = QueryRequest(**_deep_serialize(parsed.output))
        else:
            # attempt coercion
            query_request = QueryRequest(**_deep_serialize(parsed.output))

        # ensure user id is set
        query_request.user_id = user_id
    except Exception as e:
        logger.exception("[PARSER_ERROR] %s", e)
        return NLPResponse(user_id=user_id, answer="Sorry — I couldn't understand that query.", context={"error": str(e)})

    # 2) Execute the query
    try:
        query_result = await run_query(query_request)
    except Exception as e:
        logger.exception("[RUN_QUERY_ERROR] %s", e)
        return NLPResponse(user_id=user_id, answer="Sorry — I couldn't fetch data right now.", context={"error": str(e)})

    # 3) Ask the answer agent to produce a friendly answer
    try:
        payload = {"user_query": user_input, "db_result": _deep_serialize(query_result), "user_id": user_id}
        answered = await query_answer_agent.run(payload)

        # Interpret the agent's response
        if hasattr(answered, "output") and getattr(answered, "output"):
            if isinstance(answered.output, NLPResponse):
                return answered.output
            elif isinstance(answered.output, dict):
                return NLPResponse(**_deep_serialize(answered.output))

        if isinstance(answered, NLPResponse):
            return answered

        # Fall back to trying to coerce dict/other to NLPResponse
        if isinstance(answered, dict):
            return NLPResponse(**_deep_serialize(answered))

        # last resort: stringify
        return NLPResponse(user_id=user_id, answer=str(answered), context=None)

    except Exception as e:
        logger.exception("[ANSWER_AGENT_ERROR] %s", e)
        return NLPResponse(user_id=user_id, answer="I found the data but couldn't format it.", context={"db_result": _deep_serialize(query_result), "error": str(e)})


