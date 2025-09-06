# FILE: services/query_parser.py
"""
Robust query parsing entrypoint used by the FastAPI service.
Fixes and changes compared to previous version:
- Correct ordering: validate input BEFORE using undefined variables.
- Truncate/normalize input safely.
- Normalize user_id (attempt int, else keep string).
- Delegate to agents.query_agent.handle_query and coerce/validate outputs into NLPResponse.
"""

import logging
import time
from typing import Any

from agents.query_agent import handle_query
from models.query import NLPResponse
from services.date_resolver import resolve_expression

# Service-level logger
logger = logging.getLogger("query_parser_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler("query_service.log")
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)

MAX_INPUT_LEN = 2000  # protect tokens / quotas



async def parse_query(user_input: str, user_id: Any) -> NLPResponse:
    start_ts = time.perf_counter()
    truncated = False

    try:
        # Basic presence/typing checks
        if user_input is None:
            logger.warning("[PARSE_QUERY] empty user_input received")
            return NLPResponse(
                user_id=user_id,
                answer="I didn't receive any query — could you please ask that again?",
                context={"error": "empty_input"},
            )

        if not isinstance(user_input, str):
            user_input = str(user_input)

        user_input = user_input.strip()
        if not user_input:
            logger.info("[PARSE_QUERY] blank/whitespace-only input")
            return NLPResponse(
                user_id=user_id,
                answer="I couldn't understand that — please type your question or expense details.",
                context={"error": "blank_input"},
            )

        # Truncate very long inputs
        if len(user_input) > MAX_INPUT_LEN:
            truncated = True
            original_len = len(user_input)
            user_input = user_input[:MAX_INPUT_LEN]
            logger.warning(
                "[PARSE_QUERY] input_truncated user_id=%s original_len=%d max_len=%d",
                str(user_id), original_len, MAX_INPUT_LEN,
            )

        # Normalize user id (prefer int when possible, else fall back to string/UUID)
        try:
            normalized_user_id = int(user_id)
        except Exception:
            normalized_user_id = user_id
            logger.debug("[PARSE_QUERY] user_id not convertible to int; using raw value")

    except Exception as ex:
        logger.exception("[PARSE_QUERY] pre-flight validation error: %s", ex)
        return NLPResponse(
            user_id=user_id,
            answer="There was a problem understanding your request. Please try again.",
            context={"error": "validation_error", "detail": str(ex)},
        )
    # --- DATE RESOLUTION LOGIC ---
    date_info = resolve_expression(user_input)
    if date_info:
        logger.info(
            "[PARSE_QUERY] date_expression_resolved user_id=%s input='%s' -> %s",
            str(normalized_user_id),
            user_input,
            date_info,
        )

        # Optionally: replace words like "today"/"yesterday" in the input
        # with concrete dates to prevent LLM hallucination
        if "start_date" in date_info and "end_date" in date_info:
            # Only replace common keywords (keeps input natural otherwise)
            user_input = (
                user_input.replace("today", date_info["start_date"])
                          .replace("yesterday", date_info["start_date"])
                          .replace("this week", f"{date_info['start_date']} to {date_info['end_date']}")
                          .replace("last week", f"{date_info['start_date']} to {date_info['end_date']}")
                          .replace("this month", f"{date_info['start_date']} to {date_info['end_date']}")
                          .replace("last month", f"{date_info['start_date']} to {date_info['end_date']}")
            )

    # Delegate to the query agent
    try:
        result = await handle_query(user_input, normalized_user_id, context={"date_info": date_info} if date_info else None)
    except Exception as ex:
        logger.exception("[PARSE_QUERY] handle_query failed user_id=%s error=%s", str(user_id), ex)
        return NLPResponse(
            user_id=user_id,
            answer="Sorry — I couldn't fetch your data right now. Please try again in a moment.",
            context={"error": "internal_error", "detail": str(ex)},
        )

    # Coerce/validate the agent's response into NLPResponse
    try:
        if isinstance(result, NLPResponse):
            final = result
        elif isinstance(result, dict):
            final = NLPResponse(**result)
        else:
            # Fallback: represent whatever came back as an answer string
            final = NLPResponse(
                user_id=user_id,
                answer=str(result),
                context={"warning": "unexpected_result_type", "type": type(result).__name__},
            )

    except Exception as ex:
        logger.exception("[PARSE_QUERY] result validation failed user_id=%s err=%s", str(user_id), ex)
        return NLPResponse(
            user_id=user_id,
            answer="I received an unexpected response while processing your request. Please try again.",
            context={"error": "response_validation_failed", "detail": str(ex)},
        )

    # annotate truncation if required
    if truncated:
        ctx = final.context or {}
        ctx["_truncated_input"] = True
        final.context = ctx

    duration = time.perf_counter() - start_ts
    logger.info("[PARSE_QUERY] completed user_id=%s duration=%.3fs truncated=%s", str(user_id), duration, truncated)

    return final
