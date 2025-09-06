# FILE: agents/query_answer.py

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from models.query import NLPResponse
from config import GOOGLE_API_KEY
import logging
from models.query import QueryResult, NLPResponse
import json


# -----------------------------
# LLM Provider / Model
# -----------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel("gemini-1.5-flash", provider=provider)

# -----------------------------
# Query Answer Agent: System Prompt
# -----------------------------
SYSTEM_PROMPT = """
You are a Query Answer Agent. Your task is to transform structured database query results 
into clear, concise, and professional natural-language answers for users. 

Input JSON:
- user_query (string): original text query
- db_result (object): database output
    - rows (array of objects) with optional fields:
        - date, amount, category, subcategory, companions, paymentMethod, etc.
    - aggregate_result (object or null): may include sum, avg, count, min, max
    - meta (object or null): additional context like filters or notes
- user_id (string): ID of the user who requested the data

Rules:
1. Produce concise, professional, friendly answers.
2. Summarize aggregates clearly (sum, avg, count).
3. Summarize grouped data in plain language.
4. Include companions if present.
5. If no rows or aggregates, say politely: "There are no matching records."
6. Do NOT include raw JSON, DB schema, or internal notes.
7. Output strictly in NLPResponse JSON schema:
{
  "user_id": "<same user_id>",
  "answer": "<friendly natural-language answer>",
  "context": { ... optional structured info ... },
  "query": null,
  "output": null
}

Always validate:
- user_id matches input
- answer is non-empty
- context is optional but can include summaries
"""

# -----------------------------
# Query Answer Agent
# -----------------------------
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
# Async wrapper
# -----------------------------
async def answer_query(user_query: str, db_result: QueryResult, user_id: str) -> NLPResponse:
    try:
        # Combine all inputs into one dict
        input_payload = {
            "user_query": user_query,
            "db_result": db_result.dict(),
            "user_id": user_id
        }

        # Send as a single string
        raw_output = await query_answer_agent.run(json.dumps(input_payload))

        # Extract NLPResponse
        if hasattr(raw_output, "output") and raw_output.output:
            nlp_resp = raw_output.output
            if isinstance(nlp_resp, dict):
                nlp_resp["user_id"] = user_id
                return NLPResponse(**nlp_resp)
            elif isinstance(nlp_resp, NLPResponse):
                nlp_resp.user_id = user_id
                return nlp_resp

        return NLPResponse(user_id=user_id, answer="There are no matching records.")

    except Exception as e:
        import logging
        logger = logging.getLogger("query_answer_agent")
        logger.exception("[ANSWER_AGENT_ERROR] %s", e)
        return NLPResponse(user_id=user_id, answer="There was an error generating the answer.")
