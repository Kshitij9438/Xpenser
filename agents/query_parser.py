"""
PHASE 1 CRITICAL FIXES - Enhanced Query Parser (LOCKED)

This module converts natural language queries into structured QueryRequest
objects using a deterministic + LLM hybrid strategy.

Design guarantees:
- Deterministic signals always override LLM guesses
- QueryRequest is ALWAYS valid on exit
- No silent failures
"""

import logging
import asyncio
import time
from typing import Any, Dict, Optional

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from models.query import QueryRequest, QueryFilters
from services.preparser import pre_parse
from services.canonicalizer import canonicalize_category
from config import GOOGLE_API_KEY, GEMINI_MODEL_NAME

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logger = logging.getLogger("query_parser")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_parser.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# ---------------------------------------------------------------------
# Ranking Intent Detection (CRITICAL FIX)
# ---------------------------------------------------------------------
RANKING_KEYWORDS = {
    "heaviest",
    "largest",
    "highest",
    "top",
    "biggest",
    "most expensive",
    "maximum",
}

# ---------------------------------------------------------------------
# API Rate Limiting
# ---------------------------------------------------------------------
class APIRateLimiter:
    def __init__(self, max_requests_per_minute: int = 15):
        self.max_requests = max_requests_per_minute
        self.timestamps: list[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.time()
            self.timestamps = [t for t in self.timestamps if now - t < 60]

            if len(self.timestamps) >= self.max_requests:
                wait_time = 60 - (now - min(self.timestamps)) + 1
                logger.warning(f"Rate limit hit, sleeping {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

            self.timestamps.append(time.time())


_rate_limiter = APIRateLimiter()


def with_rate_limiting(fn):
    async def wrapper(*args, **kwargs):
        await _rate_limiter.acquire()
        return await fn(*args, **kwargs)
    return wrapper

# ---------------------------------------------------------------------
# User ID Validation
# ---------------------------------------------------------------------
def validate_user_id(user_id: Any) -> str:
    if user_id is None:
        raise ValueError("user_id cannot be None")

    if not isinstance(user_id, str):
        user_id = str(user_id)

    user_id = user_id.strip()
    if not user_id:
        raise ValueError("user_id cannot be empty")

    return user_id

# ---------------------------------------------------------------------
# Payment Method Canonicalization
# ---------------------------------------------------------------------
def canonicalize_payment_method(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None

    raw = raw.lower().strip()
    mapping = {
        "cash": "Cash",
        "credit card": "Credit Card",
        "debit card": "Debit Card",
        "card": "Card",
        "bank transfer": "Bank Transfer",
        "google pay": "Google Pay",
        "gpay": "Google Pay",
        "upi": "UPI",
        "paypal": "PayPal",
        "check": "Check",
        "cheque": "Check",
    }

    for k, v in mapping.items():
        if k in raw:
            return v

    return raw.title()

# ---------------------------------------------------------------------
# LLM Setup
# ---------------------------------------------------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel(GEMINI_MODEL_NAME, provider=provider)

SYSTEM_PROMPT = """
You are a Query Parser Agent.

Convert user natural language into JSON matching the QueryRequest schema.

Rules:
1. ALWAYS include user_id exactly
2. Only valid filters: category, subcategory, companions, paymentMethod,
   min_amount, max_amount, date_range.start, date_range.end
3. Aggregate only numeric fields (amount)
4. Output STRICT JSON matching the schema
5. Do not hallucinate filters
"""

query_parser_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=QueryRequest,
)

# ---------------------------------------------------------------------
# Safe Construction
# ---------------------------------------------------------------------
def _safe_query_request(data: Dict[str, Any], user_id: str) -> QueryRequest:
    data["user_id"] = validate_user_id(user_id)

    if not data.get("filters"):
        data["filters"] = {}

    if "extras" not in data["filters"] or data["filters"]["extras"] is None:
        data["filters"]["extras"] = {}

    qr = QueryRequest(**data)

    canonical = {
        "category": canonicalize_category(qr.filters.category)
        if qr.filters and qr.filters.category else None,
        "paymentMethod": canonicalize_payment_method(qr.filters.paymentMethod)
        if qr.filters else None,
    }

    qr.filters.extras["canonical"] = canonical
    return qr

# ---------------------------------------------------------------------
# Reconciliation Logic (FIXED)
# ---------------------------------------------------------------------
def _reconcile(parsed: QueryRequest, pre: Dict[str, Any], user_id: str) -> QueryRequest:
    base = parsed.model_dump(deep=True)

    filters = base.setdefault("filters", {})
    extras = filters.setdefault("extras", {})
    extras["sources"] = {}

    if pre.get("limit") is not None:
        base["limit"] = pre["limit"]
        extras["sources"]["limit"] = "deterministic"

    for key in ("min_amount", "max_amount", "date_range"):
        if pre.get(key) is not None:
            filters[key] = pre[key]
            extras["sources"][key] = "deterministic"

    if pre.get("companions"):
        filters["companions"] = pre["companions"]
        extras["sources"]["companions"] = "deterministic"

    if pre.get("payment_methods"):
        filters["paymentMethod"] = pre["payment_methods"][0]
        extras["sources"]["paymentMethod"] = "deterministic"

    if pre.get("candidate_categories"):
        filters["category"] = pre["candidate_categories"][0]
        extras["sources"]["category"] = "deterministic"

    # -------------------------------------------------
    # RANKING INTENT OVERRIDE (AUTHORITATIVE)
    # -------------------------------------------------
    text = pre.get("raw_text", "").lower()
    is_ranking = any(k in text for k in RANKING_KEYWORDS)

    if is_ranking:
        base["sort_by"] = "amount"
        base["sort_order"] = "desc"
        base["aggregate"] = None
        base["group_by"] = None
        extras["sources"]["ranking"] = "deterministic"

    return _safe_query_request(base, user_id)

# ---------------------------------------------------------------------
# Fallback Construction (FIXED)
# ---------------------------------------------------------------------
def _fallback_query(pre: Dict[str, Any], user_text: str, user_id: str) -> QueryRequest:
    filters = QueryFilters()

    if pre.get("date_range"):
        filters.date_range = pre["date_range"]
    if pre.get("companions"):
        filters.companions = pre["companions"]
    if pre.get("payment_methods"):
        filters.paymentMethod = pre["payment_methods"][0]
    if pre.get("candidate_categories"):
        filters.category = pre["candidate_categories"][0]

    text = user_text.lower()
    is_ranking = any(k in text for k in RANKING_KEYWORDS)

    aggregate = None
    if not is_ranking:
        if any(k in text for k in ("sum", "total", "spent")):
            aggregate = "sum"
        elif any(k in text for k in ("average", "avg")):
            aggregate = "avg"
        elif any(k in text for k in ("count", "how many")):
            aggregate = "count"

    return QueryRequest(
        user_id=user_id,
        filters=filters,
        aggregate=aggregate,
        aggregate_field="amount",
        limit=pre.get("limit", 100),
        offset=0,
        sort_by="amount" if is_ranking else "date",
        sort_order="desc",
    )

# ---------------------------------------------------------------------
# Main Entry
# ---------------------------------------------------------------------
@with_rate_limiting
async def parse_query_with_fallback(
    user_input: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None,
) -> QueryRequest:
    user_id = validate_user_id(user_id)
    pre = pre_parse(user_input)
    logger.info(f"Pre-parse: {pre}")

    enriched_prompt = f"User query: {user_input}\nUser ID: {user_id}"

    try:
        parsed = await query_parser_agent.run(enriched_prompt)
        logger.info("LLM parse successful")
        return _reconcile(parsed.output, pre, user_id)

    except Exception as e:
        logger.warning(f"LLM failed, using fallback: {e}")
        return _fallback_query(pre, user_input, user_id)

# ---------------------------------------------------------------------
# Backward Compatibility
# ---------------------------------------------------------------------
async def parse_query(
    user_input: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None,
) -> QueryRequest:
    return await parse_query_with_fallback(user_input, user_id, context)
