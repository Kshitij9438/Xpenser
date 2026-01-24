# tests/api/test_success_response_contract.py

import pytest
from fastapi.testclient import TestClient
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# ------------------------------------------------------------
# HARD ISOLATION: prevent heavy deps from loading
# ------------------------------------------------------------
sys.modules["prisma"] = MagicMock()

from API_LAYER.app import app

client = TestClient(app)


# ------------------------------------------------------------
# Canonical mock responses (contract-authoritative)
# ------------------------------------------------------------
MOCK_EXPENSE_RESPONSE = {
    "type": "expense",
    "data": {"amount": 200, "category": "Food"},
    "message": "Expense recorded successfully",
}

MOCK_QUERY_RESPONSE = {
    "type": "query",
    "data": {"rows": []},
    "message": "Here are your results",
}

MOCK_CONVERSATION_RESPONSE = {
    "type": "conversation",
    "data": {"conversation_type": "greeting"},
    "message": "Hello! How can I help you?",
}


@pytest.mark.parametrize(
    "payload, mock_route, mock_response",
    [
        (
            {"text": "Spent 200 rupees on lunch", "user_id": "test-user"},
            1,  # expense
            MOCK_EXPENSE_RESPONSE,
        ),
        (
            {"text": "How much did I spend on food?", "user_id": "test-user"},
            2,  # query
            MOCK_QUERY_RESPONSE,
        ),
        (
            {"text": "Hello there!", "user_id": "test-user"},
            3,  # conversation
            MOCK_CONVERSATION_RESPONSE,
        ),
    ],
)
def test_success_response_has_minimal_contract(
    payload, mock_route, mock_response
):
    """
    PHASE 5.1 — API Contract Test (SUCCESS PATH)

    This test enforces the *minimal success envelope*
    for /process, independent of internal execution.
    """

    # --------------------------------------------------------
    # Patch routing + executors at the API boundary
    # --------------------------------------------------------
    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route, \
         patch("API_LAYER.app.DB_CONNECTED",True),\
         patch("API_LAYER.app.expense_executor", new=MagicMock()) as mock_expense_exec, \
         patch("API_LAYER.app.query_executor", new=MagicMock()) as mock_query_exec, \
         patch("API_LAYER.app.conversation_executor", new=MagicMock()) as mock_conv_exec:

        # Fake router result
        mock_get_route.return_value = MagicMock(route=mock_route)

        # Fake executor responses
        mock_expense_exec.execute = AsyncMock(return_value=MOCK_EXPENSE_RESPONSE)
        mock_query_exec.execute = AsyncMock(return_value=MOCK_QUERY_RESPONSE)
        mock_conv_exec.execute = AsyncMock(return_value=MOCK_CONVERSATION_RESPONSE)

        # ----------------------------------------------------
        # Call API
        # ----------------------------------------------------
        response = client.post("/process", json=payload)

    # --------------------------------------------------------
    # HTTP Layer
    # --------------------------------------------------------
    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # JSON Layer
    # --------------------------------------------------------
    body = response.json()
    assert isinstance(body, dict), "Response must be a JSON object"

    # --------------------------------------------------------
    # CONTRACT (THE CORE)
    # --------------------------------------------------------
    for key in ("type", "data", "message"):
        assert key in body, f"Missing required key: '{key}'"

    assert isinstance(body["type"], str), "'type' must be a string"
    assert isinstance(body["message"], str), "'message' must be a string"

    # data must be JSON-serializable
    import json
    json.dumps(body["data"])
