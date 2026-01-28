# services/query_orchestrator.py

import logging
from typing import Optional, Dict, Any

from fastapi import HTTPException
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
from services.query_semantic_validator import validate_query_semantics

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

    GUARANTEES:
    - answer_query returns STRING ONLY
    - NLPResponse is constructed exactly once
    - Data ↔ answer consistency enforced
    """

    logger.info(f"[ORCH] user={user_id} | text='{user_text}'")

    try:
        # -------------------------------------------------
        # 1. PARSE → DRAFT
        # -------------------------------------------------
        draft: Dict[str, Any] = await parse_query(user_text, user_id)
        logger.info(f"[ORCH] Parsed QueryDraft: {draft}")

        # -------------------------------------------------
        # 2. SEMANTIC INVARIANTS
        # -------------------------------------------------
        validate_query_semantics(draft)

        # -------------------------------------------------
        # 3. RESOLVE SHAPE
        # -------------------------------------------------
        shape = resolve_query_shape(draft)
        logger.info(f"[SHAPE] Resolved query shape: {shape}")

        # -------------------------------------------------
        # 4. CONSTRUCT QUERY REQUEST
        # -------------------------------------------------
        query = QueryRequest(**draft, shape=shape)
        logger.info(f"[ORCH] Constructed QueryRequest: {query}")

        # -------------------------------------------------
        # 5. EXECUTE (DATA AUTHORITY)
        # -------------------------------------------------
        result: QueryResult = await run_query(prisma_db, query)
        logger.info(f"[ORCH] QueryResult: {result}")

        # -------------------------------------------------
        # 6. ANSWER (STRING ONLY)
        # -------------------------------------------------
        answer_text: str = await answer_query(
            user_text,
            result,
            user_id,
        )

        response = NLPResponse(
            user_id=user_id,
            answer=answer_text,
            query=query,
            output=result,
        )

        # -------------------------------------------------
        # 7. VALIDATE ANSWER ↔ DATA
        # -------------------------------------------------
        validate_query_response(result, response, user_text)

        return response

    # =====================================================
    # HTTP / SEMANTIC ERRORS
    # =====================================================
    except HTTPException:
        raise

    # =====================================================
    # FAIL-SAFE (NEVER BREAK USER)
    # =====================================================
    except Exception as e:
        logger.exception("[ORCH][UNEXPECTED_ERROR] %s", e)

        return NLPResponse(
            user_id=user_id,
            answer="Something went wrong while processing your request. Please try again.",
            context={
                "error": "unexpected_error",
                "source": "query_orchestrator",
            },
        )
