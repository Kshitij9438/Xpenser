"""
Query Answer Generator (v2.0 — LOCKED)

Responsibility:
- Convert QueryResult into human-readable answers
- Numeric authority is STRICTLY Python
- LLM is NOT allowed to invent or restate facts

IMPORTANT:
- This module returns ONLY strings
- Response object construction is owned by Query Orchestrator
"""

import logging
from datetime import datetime
from typing import Any

from models.query import QueryResult

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logger = logging.getLogger("query_answer")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_answer.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _format_date(val: Any) -> str:
    if not val:
        return "unknown date"
    if isinstance(val, str):
        return val[:10]
    if isinstance(val, datetime):
        return val.date().isoformat()
    return str(val)


# ---------------------------------------------------------------------
# Core Answer Generator
# ---------------------------------------------------------------------
async def answer_query(
    user_query: str,
    result: QueryResult,
    user_id: str,
) -> str:
    """
    Deterministically generates answers from QueryResult.

    HARD GUARANTEES:
    - No hallucinated numbers
    - No inferred intent
    - Output always matches data
    """

    # -------------------------------------------------
    # 1. AGGREGATE ANSWERS (STRICT TEMPLATE)
    # -------------------------------------------------
    if result.aggregate_result:
        for key, value in result.aggregate_result.items():
            if key == "sum":
                return f"Total amount spent: ₹{value:,.2f}"
            if key == "avg":
                return f"Average amount: ₹{value:,.2f}"
            if key == "count":
                return f"Found {value} matching records."
            if key == "min":
                return f"Minimum amount: ₹{value:,.2f}"
            if key == "max":
                return f"Maximum amount: ₹{value:,.2f}"

            return f"{key.capitalize()}: {value}"

    # -------------------------------------------------
    # 2. LIST / RANKING ANSWERS
    # -------------------------------------------------
    if result.rows:
        lines = []

        for idx, row in enumerate(result.rows, start=1):
            amount = row.get("amount")
            category = row.get("category", "unknown")
            date = _format_date(row.get("date"))
            desc = row.get("description") or ""

            line = f"{idx}. ₹{amount:,.0f} — {category} on {date}"
            if desc:
                line += f" ({desc})"

            lines.append(line)

        return "Here are the matching transactions:\n" + "\n".join(lines)

    # -------------------------------------------------
    # 3. EMPTY RESULT
    # -------------------------------------------------
    return "No matching records found."
