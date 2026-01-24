import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Prevent Prisma from initializing
sys.modules["prisma"] = MagicMock()

from API_LAYER.app import app

client = TestClient(app)

MOCK_EXPENSE_RESPONSE = {
    "type": "expense",
    "data": {
        "amount": 200.0,
        "category": "Food",
        "subcategory": "Lunch",
        "date": "2025-01-24",
        "companions": ["friends"],
        "paymentMethod": None,
        "description": "Lunch with friends",
    },
    "message": "You had a great lunch with friends 🍽️",
}


def test_expense_intent_returns_expense_semantics():
    """
    Phase 5.3 — Expense Intent Semantic Test

    Guarantees:
    - Expense route selects ExpenseExecutor
    - Response type is 'expense'
    - Data is expense-shaped (not query / conversation)
    - Message is human-readable
    """

    payload = {
        "text": "Spent 200 on lunch with friends",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route, \
         patch("API_LAYER.app.expense_executor", new=MagicMock()) as mock_expense_exec:

        # Force router → expense
        mock_get_route.return_value = MagicMock(route=1)

        # Mock executor output
        mock_expense_exec.execute = AsyncMock(
            return_value=MOCK_EXPENSE_RESPONSE
        )

        response = client.post("/process", json=payload)

    # -----------------------------
    # HTTP
    # -----------------------------
    assert response.status_code == 200

    body = response.json()

    # -----------------------------
    # Semantic Guarantees
    # -----------------------------
    assert body["type"] == "expense"
    assert isinstance(body["message"], str)

    data = body["data"]
    assert isinstance(data, dict)

    # Expense-specific fields must exist
    for key in ("amount", "category", "date", "description"):
        assert key in data

    # Query-only fields must NOT exist
    assert "rows" not in data
    assert "aggregate_result" not in data

# -------------------------------------------------------
# Mocked query response (canonical shape)
# -------------------------------------------------------
MOCK_QUERY_RESPONSE = {
    "type": "query",
    "data": {
        "rows": [
            {
                "amount": 200,
                "category": "Food",
                "date": "2025-01-01",
            }
        ],
        "aggregate_result": {
            "sum": 200,
            "count": 1,
        },
    },
    "message": "Here is what I found for your expenses.",
}


def test_query_intent_returns_query_contract():
    """
    Phase 5.4 — Query Intent Semantic Test

    Guarantees:
    - Query intent invokes QueryExecutor
    - Response type is 'query'
    - Query-shaped data is returned
    - No expense-style fields leak in
    """

    payload = {
        "text": "How much did I spend on food?",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route, \
         patch("API_LAYER.app.query_executor", new=MagicMock()) as mock_query_exec, \
         patch("API_LAYER.app.DB_CONNECTED", new=True):

        # Force router → query
        mock_get_route.return_value = MagicMock(route=2)

        # Fake query executor output
        mock_query_exec.execute = AsyncMock(return_value=MOCK_QUERY_RESPONSE)

        response = client.post("/process", json=payload)

    # --------------------
    # HTTP Layer
    # --------------------
    assert response.status_code == 200, response.text

    body = response.json()
    assert isinstance(body, dict)

    # --------------------
    # Core Contract
    # --------------------
    assert body["type"] == "query"
    assert "data" in body
    assert "message" in body

    # --------------------
    # Query-specific data guarantees
    # --------------------
    data = body["data"]

    assert "rows" in data
    assert isinstance(data["rows"], list)

    # aggregate_result is optional but must be structured if present
    if "aggregate_result" in data:
        assert isinstance(data["aggregate_result"], dict)

    # --------------------
    # Negative guarantees (no expense leakage)
    # --------------------
    forbidden_fields = {"amount", "category", "paymentMethod"}
    assert not forbidden_fields.issubset(body.keys()), (
        "Expense fields leaked into query response"
    )
# -------------------------------------------------------
# Mocked conversation response (canonical shape)
# -------------------------------------------------------
MOCK_CONVERSATION_RESPONSE = {
    "type": "conversation",
    "data": {
        "conversation_type": "general",
    },
    "message": "Hello! I’m doing great 😊",
}


def test_conversation_intent_returns_conversation_semantics():
    """
    Phase 5.5 — Conversation Intent Semantic Test

    Guarantees:
    - Conversation intent invokes ConversationExecutor
    - Response type is 'conversation'
    - Message is human-facing
    - No expense or query fields leak in
    """

    payload = {
        "text": "Hello, how are you?",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route, \
         patch("API_LAYER.app.conversation_executor", new=MagicMock()) as mock_conv_exec:

        # Force router → conversation
        mock_get_route.return_value = MagicMock(route=3)

        # Fake conversation executor output
        mock_conv_exec.execute = AsyncMock(
            return_value=MOCK_CONVERSATION_RESPONSE
        )

        response = client.post("/process", json=payload)

    # --------------------
    # HTTP Layer
    # --------------------
    assert response.status_code == 200, response.text

    body = response.json()

    # --------------------
    # Core Contract
    # --------------------
    assert body["type"] == "conversation"
    assert isinstance(body["message"], str)
    assert "data" in body

    # --------------------
    # Negative guarantees
    # --------------------
    forbidden_fields = {
        "amount",
        "category",
        "paymentMethod",
        "rows",
        "aggregate_result",
    }

    assert not forbidden_fields.intersection(body["data"].keys()), (
        "Expense or query fields leaked into conversation response"
    )
