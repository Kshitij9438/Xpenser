# FILE: agents/query_parser.py
import logging
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from models.query import QueryRequest
from config import GOOGLE_API_KEY
from typing import Optional, Dict, Any
# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("query_parser_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_parser.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# -----------------------------
# LLM Provider / Model
# -----------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel("gemini-1.5-flash", provider=provider)

# -----------------------------
# System prompt with DB schema
# -----------------------------
SYSTEM_PROMPT = """
You are a Query Parser Agent. Convert user natural language into JSON matching the QueryRequest schema.

Your database table `Expense` has these columns:

- id: String
- user_id: String
- amount: Decimal (numeric, can aggregate)
- category: String
- subcategory: String? (optional)
- date: DateTime
- paymentMethod: String? (optional)
- description: String? (optional)
- createdAt: DateTime
- companions: String[] (array of strings)

Rules:
1. Always include "user_id".
2. Only use these filters: category, subcategory, companions, paymentMethod, min_amount, max_amount, date_range.start, date_range.end
3. Aggregate only numeric fields: amount
4. group_by is allowed only on scalar fields (cannot group_by companions)
5. Output strictly JSON matching QueryRequest schema
6. Provide defaults where necessary: limit=100, offset=0, aggregate_field='amount', sort_order='desc'

Examples:

User: "How much did I spend last month?" (user_id=22f8e821)
Output:
{
  "user_id": "22f8e821",
  "filters": {
    "date_range": {"start": "2025-08-01", "end": "2025-08-31"}
  },
  "aggregate": "sum",
  "aggregate_field": "amount",
  "group_by": null,
  "limit": 100,
  "offset": 0,
  "sort_by": "date",
  "sort_order": "desc"
}

User: "Show all my food expenses with Alice" (user_id=22f8e821)
Output:
{
  "user_id": "22f8e821",
  "filters": {
    "category": "Food",
    "companions": ["Alice"]
  },
  "aggregate": null,
  "aggregate_field": "amount",
  "group_by": null,
  "limit": 100,
  "offset": 0,
  "sort_by": "date",
  "sort_order": "desc"
}
"""

# -----------------------------
# Query Parser Agent
# -----------------------------
query_parser_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=QueryRequest,
)

# -----------------------------
# Async wrapper
# -----------------------------
async def parse_query(user_input: str, user_id: str,context: Optional[Dict[str, Any]] = None) -> QueryRequest:
    """
    Convert natural language query + user_id -> QueryRequest
    """
    try:
        # Ask the LLM to parse user input
        raw_output = await query_parser_agent.run(f"User (id={user_id}) asked: {user_input}")

        # Extract QueryRequest from raw output
        if hasattr(raw_output, "output") and raw_output.output:
            qr = raw_output.output
            if isinstance(qr, dict):
                return QueryRequest(**qr, user_id=user_id)
            elif isinstance(qr, QueryRequest):
                qr.user_id = user_id
                return qr

        # fallback: minimal QueryRequest
        return QueryRequest(user_id=user_id)

    except Exception as e:
        logger.exception("[PARSER_ERROR] %s", e)
        # return minimal QueryRequest on failure
        return QueryRequest(user_id=user_id)
