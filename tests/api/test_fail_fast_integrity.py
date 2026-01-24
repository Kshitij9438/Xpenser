# tests/api/test_fail_fast_integrity.py

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Prevent Prisma init
sys.modules["prisma"] = MagicMock()

from API_LAYER.app import app, request_counters

client = TestClient(app)


def test_router_failure_fails_fast_without_executor_calls():
    payload = {
        "text": "Anything",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_router, \
         patch("API_LAYER.app.expense_executor") as mock_expense, \
         patch("API_LAYER.app.query_executor") as mock_query, \
         patch("API_LAYER.app.conversation_executor") as mock_conv:

        mock_router.side_effect = RuntimeError("router exploded")

        response = client.post("/process", json=payload)

    # ---- HTTP ----
    assert response.status_code == 500

    body = response.json()
    assert "error" in body

    # ---- FAIL-FAST GUARANTEES ----
    mock_expense.execute.assert_not_called()
    mock_query.execute.assert_not_called()
    mock_conv.execute.assert_not_called()
def test_executor_failure_does_not_cascade():
    payload = {
        "text": "Spent 200 on lunch",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_router, \
         patch("API_LAYER.app.expense_executor") as mock_expense, \
         patch("API_LAYER.app.query_executor") as mock_query:

        mock_router.return_value = MagicMock(route=1)
        mock_expense.execute = AsyncMock(side_effect=RuntimeError("boom"))

        response = client.post("/process", json=payload)

    assert response.status_code == 500
    body = response.json()
    assert "error" in body

    # ---- FAIL-FAST ----
    mock_query.execute.assert_not_called()
def test_metrics_not_corrupted_on_failure():
    before = request_counters.copy()

    payload = {
        "text": "Hello",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_router:
        mock_router.side_effect = RuntimeError("fail early")

        response = client.post("/process", json=payload)

    assert response.status_code == 500

    after = request_counters.copy()

    # ---- METRICS INTEGRITY ----
    assert after["errors"] == before["errors"] + 1
    assert after["expense"] == before["expense"]
    assert after["query"] == before["query"]
    assert after["unknown"] == before["unknown"]
