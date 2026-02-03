# ---------------------------------------------------------------------
# PHASE 2 — Query Parser → Intent Draft (LOCKED)
# ---------------------------------------------------------------------

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
# Keyword Sets (AUTHORITATIVE SIGNALS)
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

AGGREGATE_KEYWORDS = {
    "sum",
    "total",
    "spent",
    "average",
    "avg",
    "count",
    "how much",
    "how many",
}

LIST_KEYWORDS = {
    "show",
    "list",
    "display",
    "expenses",
    "transactions",
    "records",
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
# LLM Setup
# ---------------------------------------------------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel(GEMINI_MODEL_NAME, provider=provider)

SYSTEM_PROMPT = """
You are a Query Parser Agent.

Extract intent hints ONLY.

Do NOT:
- Resolve query shape
- Enforce execution invariants
- Guess user intent

Return partial hints if unsure.
"""

query_parser_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=dict,
)

# ---------------------------------------------------------------------
# Reconciliation Logic (CORE)
# ---------------------------------------------------------------------
def _reconcile(
    parsed: Dict[str, Any],
    pre: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:

    text = pre.get("raw_text", "").lower()

    # -------------------------------------------------
    # Semantic intent detection (AUTHORITATIVE)
    # -------------------------------------------------
    is_aggregate = any(k in text for k in AGGREGATE_KEYWORDS)
    is_ranking = any(k in text for k in RANKING_KEYWORDS)
    is_grouping = "grouped by" in text or "group by" in text

    # Canonical linguistic rule:
    # COUNT-style queries suppress LIST semantics
    is_count_query = ("count" in text) or ("how many" in text)

    if is_count_query:
        is_list = False
    else:
        is_list = any(k in text for k in LIST_KEYWORDS)

    semantic_intents = {
        "list": is_list,
        "aggregate": is_aggregate,
        "ranking": is_ranking,
        "grouping": is_grouping,
    }

    # -------------------------------------------------
    # Base draft (NEUTRAL, UNRESOLVED)
    # -------------------------------------------------
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
        "semantic_intents": semantic_intents,
        "extras": {"sources": {}},
    }

    filters = draft["filters"]
    sources = draft["extras"]["sources"]

    # -------------------------------------------------
    # Deterministic filters
    # -------------------------------------------------
    for key in ("min_amount", "max_amount", "date_range"):
        if pre.get(key) is not None:
            filters[key] = pre[key]
            sources[key] = "deterministic"

    if pre.get("candidate_categories"):
        filters["category"] = canonicalize_category(
            pre["candidate_categories"][0]
        )
        sources["category"] = "deterministic"

    # -------------------------------------------------
    # Aggregate execution hint (ONLY if aggregate detected)
    # -------------------------------------------------
    if semantic_intents["aggregate"]:
        if "average" in text or "avg" in text:
            draft["aggregate"] = "avg"
        elif "count" in text or "how many" in text:
            draft["aggregate"] = "count"
        else:
            draft["aggregate"] = "sum"

    # -------------------------------------------------
    # Ranking execution hint
    # -------------------------------------------------
    if semantic_intents["ranking"]:
        draft["sort_by"] = "amount"
        draft["sort_order"] = "desc"

    # -------------------------------------------------
    # LLM hints (LOW PRIORITY, NEVER authoritative)
    # -------------------------------------------------
    for k in ("group_by", "columns", "limit", "offset"):
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
