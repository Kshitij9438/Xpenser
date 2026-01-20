"""
Query Orchestrator (LOCKED)

Responsibility:
- Coordinate parsing → execution → answer generation
- Resolve query shape BEFORE execution
- Construct QueryRequest (single authority)
- Enforce hard exception boundaries
- Always return NLPResponse to callers

Philosophy:
- Developer mistakes must crash loudly
- Users must always receive structured, explainable failures
"""

import logging
from typing import Optional, Dict, Any

from prisma import Prisma

from agents.query_parser import parse_query
from agents.query_answer import answer_query

from models.query import NLPResponse, QueryRequest, QueryResult
from services.query_builder import run_query
from services.query_shape_resolver import resolve_query_shape
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
# Answer Normalization
# ---------------------------------------------------------------------
def _normalize_answer(answer: Any) -> str:
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
    Orchestrates the full deterministic query lifecycle.

    HARD GUARANTEES:
    - QueryRequest is constructed exactly once
    - Query shape is resolved BEFORE execution
    - Builder never infers intent
    - Invariant violations crash here (dev-visible)
    - UI always receives NLPResponse
    """

    logger.info(f"[ORCH] user={user_id} | text='{user_text}'")

    try:
        # -------------------------------------------------
        # 1. PARSE → QueryDraft (UNSAFE)
        # -------------------------------------------------
        draft: Dict[str, Any] = await parse_query(user_text, user_id)
        logger.info(f"[ORCH] Parsed QueryDraft: {draft}")

        # -------------------------------------------------
        # 2. RESOLVE SHAPE (AUTHORITATIVE)
        # -------------------------------------------------
        shape = resolve_query_shape(draft)
        logger.info(f"[SHAPE] Resolved query shape: {shape}")

        # -------------------------------------------------
        # 3. CONSTRUCT QueryRequest (HARD GATE)
        # -------------------------------------------------
        query = QueryRequest(**draft, shape=shape)
        logger.info(f"[ORCH] Constructed QueryRequest: {query}")

        # -------------------------------------------------
        # 4. EXECUTE (BUILDER WILL CRASH IF INVALID)
        # -------------------------------------------------
        result: QueryResult = await run_query(prisma_db, query)
        logger.info(f"[ORCH] QueryResult: {result}")

        has_rows = bool(result.rows)
        has_aggregate = bool(result.aggregate_result)

        # -------------------------------------------------
        # 5. AGGREGATE QUERIES
        # -------------------------------------------------
        if query.shape.is_aggregate():
            if not has_aggregate:
                logger.warning("[ORCH] Aggregate query returned no aggregate_result")
                return create_safe_fallback_response(result, user_id, user_text)

            raw = await answer_query(user_text, result, user_id)
            answer = _normalize_answer(raw)

            response = NLPResponse(
                user_id=user_id,
                answer=answer,
                query=query,
                output=result,
            )

            validate_query_response(result, response, user_text)
            return response

        # -------------------------------------------------
        # 6. LIST / RANKING / DETAIL QUERIES
        # -------------------------------------------------
        if has_rows:
            raw = await answer_query(user_text, result, user_id)
            answer = _normalize_answer(raw)

            response = NLPResponse(
                user_id=user_id,
                answer=answer,
                query=query,
                output=result,
            )

            validate_query_response(result, response, user_text)
            return response

        # -------------------------------------------------
        # 7. EMPTY BUT VALID
        # -------------------------------------------------
        logger.info("[ORCH] No rows returned — safe fallback")
        return create_safe_fallback_response(result, user_id, user_text)

    # =====================================================
    # 🔥 INVARIANT VIOLATIONS (CRASH LOUD, FAIL SOFT)
    # =====================================================
    except RuntimeError as e:
        logger.exception("[ORCH][INVARIANT_VIOLATION] %s", e)

        return NLPResponse(
            user_id=user_id,
            answer="I couldn’t process this request due to an internal consistency issue.",
            context={
                "error": "invariant_violation",
                "message": str(e),
            },
        )

    # =====================================================
    # 🚨 UNEXPECTED BUGS
    # =====================================================
    except Exception as e:
        logger.exception("[ORCH][UNEXPECTED_ERROR] %s", e)

        return NLPResponse(
            user_id=user_id,
            answer="Something went wrong while processing your request. Please try again.",
            context={
                "error": "unexpected_error",
                "type": type(e).__name__,
            },
        )
