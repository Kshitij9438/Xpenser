# FILE: services/query_orchestrator.py
"""
Query Orchestrator Service
- Coordinates the full query pipeline from user input to NLP response
- Imports and uses the handle_query function from agents.query_agent
"""

import logging
from typing import Any
from prisma import Prisma
from agents.query_parser import parse_query
from models.query import NLPResponse
from models.query import QueryRequest
from services.query_builder import run_query
from models.query import QueryResult
from agents.query_answer import answer_query
from typing import Optional, Dict, Any
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
    try:
        logger.info(f"Processing query for user {user_id}: {user_text}")
        parsed_result: QueryRequest = await parse_query(user_text, user_id)
        # do NOT reconnect; use the passed instance
        result: QueryResult = await run_query(prisma_db, parsed_result)
        nlp_response: NLPResponse = await answer_query(user_text, result, user_id)
        logger.info(f"NLPResponse: {nlp_response}")
        return nlp_response
    except Exception as e:
        logger.exception(f"Error handling query: {e}")
        return NLPResponse(user_id=user_id, answer="There was an error processing your query.")
