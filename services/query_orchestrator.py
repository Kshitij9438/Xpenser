# FILE: services/query_orchestrator.py
"""
Enhanced Query Orchestrator with improved validation
"""

import logging
from typing import Any, Optional, Dict
from prisma import Prisma
from agents.query_parser import parse_query
from models.query import NLPResponse, QueryRequest
from services.query_builder import run_query
from models.query import QueryResult
from agents.query_answer import answer_query
from services.query_validator import validate_query_response, create_safe_fallback_response

# -----------------------------
# Logging Setup
# -----------------------------
logger = logging.getLogger("query_orchestrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_orchestrator.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)


async def handle_user_query(user_text: str, user_id: str, prisma_db: Prisma, context: Optional[Dict[str, Any]] = None) -> NLPResponse:
    """
    Enhanced query handling with improved validation
    """
    try:
        logger.info(f"Processing query for user {user_id}: {user_text}")
        
        # Step 1: Parse query
        parsed_result: QueryRequest = await parse_query(user_text, user_id)
        logger.info(f"Parsed query: {parsed_result}")
        
        # Step 2: Execute query
        result: QueryResult = await run_query(prisma_db, parsed_result)
        logger.info(f"Query result: {result}")
        
        # Step 3: Generate answer
        nlp_response: NLPResponse = await answer_query(user_text, result, user_id)
        logger.info(f"Generated answer: {nlp_response.answer}")
        
        # Step 4: Enhanced validation with original query
        validation_warning = validate_query_response(result, nlp_response, user_text)
        if validation_warning:
            logger.warning(f"Validation warning: {validation_warning}")
            # Use safe fallback response
            return create_safe_fallback_response(result, user_id, user_text)
        
        return nlp_response
        
    except Exception as e:
        logger.exception(f"Error handling query: {e}")
        return NLPResponse(
            user_id=user_id, 
            answer="There was an error processing your query. Please try rephrasing it.",
            context={"error": str(e)}
        )
