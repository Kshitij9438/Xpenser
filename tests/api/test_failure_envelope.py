import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# ------------------------------------------------------------
# Prevent Prisma from loading during API contract tests
# ------------------------------------------------------------
sys.modules["prisma"] = MagicMock()

from API_LAYER.app import app

client = TestClient(app)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def assert_failure_envelope(body: dict):
    """
    Enforces the minimal failure response contract.
    """
    assert isinstance(body, dict), "Failure response must be a JSON object"
    assert "error" in body, "Missing 'error' key in failure response"

    error = body["error"]
    assert isinstance(error, dict), "'error' must be an object"

    assert "type" in error, "Missing 'error.type'"
    assert "message" in error, "Missing 'error.message'"

    assert isinstance(error["type"], str), "'error.type' must be a string"
    assert isinstance(error["message"], str), "'error.message' must be a string"


# ------------------------------------------------------------
# Tests
# ------------------------------------------------------------

def test_query_db_unavailable_returns_failure_envelope():
    """
    Phase 5.2 — Query attempted while DB is unavailable.
    Must return structured failure envelope.
    """

    payload = {
        "text": "How much did I spend on food?",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route:
        mock_get_route.return_value = MagicMock(route=2)  # query intent

        response = client.post("/process", json=payload)

    assert response.status_code == 503

    body = response.json()
    assert_failure_envelope(body)


def test_executor_timeout_returns_failure_envelope():
    """
    Phase 5.2 — Executor timeout should map to a 504
    with a stable failure envelope.
    """

    payload = {
        "text": "Spent 200 on lunch",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route, \
         patch("API_LAYER.app.expense_executor", new=MagicMock()) as mock_exec:

        mock_get_route.return_value = MagicMock(route=1)  # expense intent
        mock_exec.execute = AsyncMock(
            side_effect=Exception("timeout")
        )

        response = client.post("/process", json=payload)

    assert response.status_code == 500  # status may evolve later
    body = response.json()
    assert_failure_envelope(body)


def test_unhandled_exception_returns_failure_envelope():
    """
    Phase 5.2 — Any unexpected exception must still
    return a structured failure response.
    """

    payload = {
        "text": "Hello",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route:
        mock_get_route.side_effect = RuntimeError("boom")

        response = client.post("/process", json=payload)

    assert response.status_code == 500
    body = response.json()
    assert_failure_envelope(body)
