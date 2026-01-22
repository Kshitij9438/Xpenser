"""
PHASE 2 — Query Parser → Intent Draft (LOCKED)

This module converts natural language into a *QueryDraft*.
It does NOT construct QueryRequest.
It does NOT resolve shape.
It does NOT enforce execution invariants.

Design guarantees:
- Deterministic signals override LLM guesses
- No QueryRequest construction
- No execution assumptions
- No silent failures
"""

import logging
import asyncio
import time
from typing import Any, Dict, Optional

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from services.preparser import pre_parse
from services.canonicalizer import canonicalize_category
from configurations.config import GOOGLE_API_KEY, GEMINI_MODEL_NAME

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
# Ranking Intent Detection (AUTHORITATIVE)
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
    user_id = str(user_id).strip()
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

Convert user natural language into a JSON object describing INTENT ONLY.

DO NOT:
- Construct QueryRequest
- Infer execution shape
- Invent filters

Allowed keys:
- filters
- aggregate
- aggregate_field
- group_by
- columns
- sort_by
- sort_order
- limit
- offset
"""

query_parser_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=dict,
)

# ---------------------------------------------------------------------
# Reconciliation Logic (CORE)
# ---------------------------------------------------------------------
def _reconcile(parsed: Dict[str, Any], pre: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Produces a QueryDraft.
    No execution invariants enforced here.
    """

    draft: Dict[str, Any] = {
        "user_id": user_id,
        "filters": {},
        "limit": pre.get("limit", 100),
        "offset": 0,
        "aggregate": None,
        "aggregate_field": "amount",
        "group_by": None,
        "columns": None,
        "sort_by": None,
        "sort_order": "desc",
        "extras": {"sources": {}},
    }

    filters = draft["filters"]
    sources = draft["extras"]["sources"]

    # -----------------------------
    # Deterministic overrides
    # -----------------------------
    for key in ("min_amount", "max_amount", "date_range"):
        if pre.get(key) is not None:
            filters[key] = pre[key]
            sources[key] = "deterministic"

    if pre.get("companions"):
        filters["companions"] = pre["companions"]
        sources["companions"] = "deterministic"

    if pre.get("payment_methods"):
        filters["paymentMethod"] = canonicalize_payment_method(pre["payment_methods"][0])
        sources["paymentMethod"] = "deterministic"

    if pre.get("candidate_categories"):
        filters["category"] = canonicalize_category(pre["candidate_categories"][0])
        sources["category"] = "deterministic"

    # -----------------------------
    # Ranking intent (AUTHORITATIVE)
    # -----------------------------
    text = pre.get("raw_text", "").lower()
    is_ranking = any(k in text for k in RANKING_KEYWORDS)

    if is_ranking:
        draft["sort_by"] = "amount"
        draft["sort_order"] = "desc"
        sources["ranking"] = "deterministic"
    else:
        if any(k in text for k in ("sum", "total", "spent")):
            draft["aggregate"] = "sum"
        elif any(k in text for k in ("average", "avg")):
            draft["aggregate"] = "avg"
        elif any(k in text for k in ("count", "how many")):
            draft["aggregate"] = "count"

    # -----------------------------
    # LLM hints (LOW PRIORITY)
    # -----------------------------
    for k in (
        "aggregate",
        "aggregate_field",
        "group_by",
        "columns",
        "sort_by",
        "sort_order",
        "limit",
        "offset",
    ):
        if parsed.get(k) is not None and draft.get(k) is None:
            draft[k] = parsed[k]

    return draft

# ---------------------------------------------------------------------
# Main Entry
# ---------------------------------------------------------------------
@with_rate_limiting
async def parse_query(
    user_input: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns a QueryDraft (NOT QueryRequest).
    """

    user_id = validate_user_id(user_id)
    pre = pre_parse(user_input)

    logger.info(f"[PRE_PARSE] {pre}")

    try:
        llm_result = await query_parser_agent.run(
            f"User query: {user_input}\nUser ID: {user_id}"
        )
        parsed = llm_result.output or {}
        logger.info("[LLM] parse successful")
    except Exception as e:
        logger.warning("[LLM] failed, using empty intent: %s", e)
        parsed = {}

    return _reconcile(parsed, pre, user_id)
