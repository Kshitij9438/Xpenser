# FILE: test_query_answer_agent.py

import asyncio
from agents.query_answer import answer_query
from models.query import QueryResult, NLPResponse

# -----------------------------
# Step 1: Build a sample QueryResult
# -----------------------------
db_result = QueryResult(
    rows=[
        {
            "date": "2025-09-05",
            "amount": 1200,
            "category": "Travel",
            "subcategory": "Flight",
            "companions": ["Alice", "Bob"],
            "paymentMethod": "Credit Card"
        },
        {
            "date": "2025-09-03",
            "amount": 300,
            "category": "Travel",
            "subcategory": "Taxi",
            "companions": [],
            "paymentMethod": "Cash"
        }
    ],
    aggregate_result={
        "sum": 1500,
        "count": 2
    },
    meta={"note": "Includes recent travel expenses"}
)

# -----------------------------
# Step 2: Define a user query and ID
# -----------------------------
user_query = "Show me all travel expenses this week"
user_id = "user_123"

# -----------------------------
# Step 3: Async test runner
# -----------------------------
async def test_answer_agent():
    nlp_response: NLPResponse = await answer_query(user_query, db_result, user_id)
    print("Generated NLPResponse:")
    print(nlp_response)

# -----------------------------
# Step 4: Run the async test
# -----------------------------
if __name__ == "__main__":
    asyncio.run(test_answer_agent())
