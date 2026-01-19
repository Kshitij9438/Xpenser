# FILE: agents/query_answer.py

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from models.query import NLPResponse, QueryResult
from config import GOOGLE_API_KEY, GEMINI_MODEL_NAME
import logging
import json
from datetime import datetime

# -----------------------------
# LLM Provider / Model
# -----------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel(GEMINI_MODEL_NAME, provider=provider)

# -----------------------------
# Query Answer Agent: System Prompt
# -----------------------------
SYSTEM_PROMPT = """
You are a Query Answer Agent. Your task is to transform structured database query results 
into clear, concise, and professional natural-language answers for users. 

Rules:
- Be concise, grounded, and factual
- Use ₹ for currency
- Never hallucinate details not present in data
"""

query_answer_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=NLPResponse,
)

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("query_answer_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_answer.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# -----------------------------
# Helpers
# -----------------------------
def _format_date(val):
    if not val:
        return "unknown date"
    try:
        if isinstance(val, str):
            return val[:10]
        if isinstance(val, datetime):
            return val.date().isoformat()
    except Exception:
        pass
    return str(val)

# -----------------------------
# Async wrapper (FIXED)
# -----------------------------
async def answer_query(
    user_query: str,
    db_result: QueryResult,
    user_id: str
) -> NLPResponse:
    try:
        # -------------------------------------------------
        # 1. DETERMINISTIC LIST / RANKING ANSWER (CRITICAL)
        # -------------------------------------------------
        if db_result.rows and not db_result.aggregate_result:
            lines = []

            for idx, row in enumerate(db_result.rows, start=1):
                amount = row.get("amount")
                category = row.get("category", "unknown")
                date = _format_date(row.get("date"))
                desc = row.get("description") or ""

                lines.append(
                    f"{idx}. ₹{amount:,.0f} — {category} on {date}"
                    + (f" ({desc})" if desc else "")
                )

            answer = "Here are the top transactions:\n" + "\n".join(lines)

            return NLPResponse(
                user_id=user_id,
                answer=answer,
                context={"type": "ranking", "count": len(lines)}
            )

        # -------------------------------------------------
        # 2. AGGREGATE ANSWERS → LLM
        # -------------------------------------------------
        input_payload = {
            "user_query": user_query,
            "db_result": db_result.dict(),
            "user_id": user_id,
        }

        raw_output = await query_answer_agent.run(json.dumps(input_payload))

        if hasattr(raw_output, "output") and raw_output.output:
            out = raw_output.output
            if isinstance(out, NLPResponse):
                out.user_id = user_id
                return out
            if isinstance(out, dict):
                out["user_id"] = user_id
                return NLPResponse(**out)

        # -------------------------------------------------
        # 3. EMPTY RESULT (SAFE)
        # -------------------------------------------------
        return NLPResponse(
            user_id=user_id,
            answer="There are no matching records."
        )

    except Exception as e:
        logger.exception("[ANSWER_AGENT_ERROR] %s", e)
        return NLPResponse(
            user_id=user_id,
            answer="There was an issue generating the response."
        )
