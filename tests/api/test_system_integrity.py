import sys
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Prevent Prisma startup
sys.modules["prisma"] = MagicMock()

from API_LAYER.app import app

client = TestClient(app)


def test_exactly_one_executor_runs_per_request():
    """
    Phase 6.1 — System Integrity

    Guarantee:
    - Exactly ONE executor runs per request
    - Others must NOT be touched
    """

    payload = {
        "text": "Spent 200 on lunch",
        "user_id": "test-user",
    }

    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route, \
         patch("API_LAYER.app.expense_executor", new=MagicMock()) as expense_exec, \
         patch("API_LAYER.app.query_executor", new=MagicMock()) as query_exec, \
         patch("API_LAYER.app.conversation_executor", new=MagicMock()) as conv_exec:

        # Force expense route
        mock_get_route.return_value = MagicMock(route=1)

        expense_exec.execute = AsyncMock(
            return_value={
                "type": "expense",
                "data": {},
                "message": "ok",
            }
        )

        response = client.post("/process", json=payload)

    assert response.status_code == 200

    # ✅ Exactly one executor called
    expense_exec.execute.assert_called_once()
    query_exec.execute.assert_not_called()
    conv_exec.execute.assert_not_called()

def test_metrics_are_internally_consistent_on_success_and_failure():
    """
    Phase 6.2 — Metrics Integrity

    Guarantees:
    - total == expense + query + unknown + errors
    - success increments exactly one intent counter
    - failure increments only errors
    """

    from API_LAYER.app import request_counters

    # Reset metrics (IMPORTANT)
    request_counters.update({
        "expense": 0,
        "query": 0,
        "unknown": 0,
        "total": 0,
        "errors": 0,
    })

    # -----------------------------
    # SUCCESSFUL EXPENSE REQUEST
    # -----------------------------
    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route, \
         patch("API_LAYER.app.expense_executor", new=MagicMock()) as expense_exec:

        mock_get_route.return_value = MagicMock(route=1)
        expense_exec.execute = AsyncMock(
            return_value={"type": "expense", "data": {}, "message": "ok"}
        )

        client.post("/process", json={
            "text": "Spent 100",
            "user_id": "test-user",
        })

    assert request_counters["total"] == 1
    assert request_counters["expense"] == 1
    assert request_counters["errors"] == 0

    # -----------------------------
    # FAILED QUERY REQUEST
    # -----------------------------
    with patch("API_LAYER.app.get_route", new_callable=AsyncMock) as mock_get_route:

        mock_get_route.return_value = MagicMock(route=2)  # query
        client.post("/process", json={
            "text": "How much did I spend?",
            "user_id": "test-user",
        })

    assert request_counters["total"] == 2
    assert request_counters["errors"] == 1

    # No intent counters should change on failure
    assert request_counters["expense"] == 1
    assert request_counters["query"] == 0
    assert request_counters["unknown"] == 0

    # -----------------------------
    # FINAL INVARIANT
    # -----------------------------
    assert request_counters["total"] == (
        request_counters["expense"]
        + request_counters["query"]
        + request_counters["unknown"]
        + request_counters["errors"]
    )
