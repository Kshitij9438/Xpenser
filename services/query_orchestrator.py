"""
Query Orchestrator (LOCKED)

Responsibility:
- Coordinate parsing → execution → answer generation
- Decide query shape deterministically
- Guarantee safe, explainable responses
"""

import logging
from typing import Optional, Dict, Any

from prisma import Prisma

from agents.query_parser import parse_query
from agents.query_answer import answer_query
from models.query import NLPResponse, QueryRequest, QueryResult
from services.query_builder import run_query
from services.query_validator import (
    validate_query_response,
    create_safe_fallback_response,
)

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logger = logging.getLogger("query_orchestrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_orchestrator.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# ---------------------------------------------------------------------
# Answer Normalization (CRITICAL FIX)
# ---------------------------------------------------------------------
def _normalize_answer(answer: Any) -> str:
    """
    Enforces answer_query contract.

    - If answer_query returns str → use it
    - If it returns NLPResponse → extract .answer
    - Otherwise → stringify safely
    """
    if isinstance(answer, str):
        return answer
    if hasattr(answer, "answer"):
        return str(answer.answer)
    return str(answer)

# ---------------------------------------------------------------------
# Core Orchestrator
# ---------------------------------------------------------------------
async def handle_user_query(
    user_text: str,
    user_id: str,
    prisma_db: Prisma,
    context: Optional[Dict[str, Any]] = None,
) -> NLPResponse:
    """
    Orchestrates full query lifecycle.

    Contract:
    - Always returns NLPResponse
    - Never fabricates answers without data
    - Never hides empty results
    """

    logger.info(f"[ORCH] user={user_id} | text='{user_text}'")

    # -------------------------------------------------
    # 1. PARSE
    # -------------------------------------------------
    parsed: QueryRequest = await parse_query(user_text, user_id)
    logger.info(f"[ORCH] Parsed QueryRequest: {parsed}")

    # -------------------------------------------------
    # 2. EXECUTE
    # -------------------------------------------------
    result: QueryResult = await run_query(prisma_db, parsed)
    logger.info(f"[ORCH] QueryResult: {result}")

    # -------------------------------------------------
    # 3. CLASSIFY QUERY SHAPE (AUTHORITATIVE)
    # -------------------------------------------------
    is_aggregate = parsed.aggregate is not None
    has_rows = bool(result.rows)
    has_aggregate = bool(result.aggregate_result)

    logger.info(
        f"[ORCH] shape: aggregate={is_aggregate}, rows={has_rows}, agg_result={has_aggregate}"
    )

    # -------------------------------------------------
    # 4. AGGREGATE QUERIES
    # -------------------------------------------------
    if is_aggregate:
        if not has_aggregate:
            logger.warning("[ORCH] Aggregate query returned no aggregate_result")
            return create_safe_fallback_response(result, user_id, user_text)

        raw_answer = await answer_query(user_text, result, user_id)
        answer = _normalize_answer(raw_answer)

        response = NLPResponse(
            user_id=user_id,
            answer=answer,
            query=parsed,
            output=result,
        )

        validate_query_response(result, response, user_text)
        return response

    # -------------------------------------------------
    # 5. LIST / RANKING / DETAIL QUERIES
    # -------------------------------------------------
    if has_rows:
        raw_answer = await answer_query(user_text, result, user_id)
        answer = _normalize_answer(raw_answer)

        response = NLPResponse(
            user_id=user_id,
            answer=answer,
            query=parsed,
            output=result,
        )

        validate_query_response(result, response, user_text)
        return response

    # -------------------------------------------------
    # 6. EMPTY BUT VALID
    # -------------------------------------------------
    logger.info("[ORCH] No rows returned — safe fallback")
    return create_safe_fallback_response(result, user_id, user_text)
