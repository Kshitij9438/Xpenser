import pytest


def test_aggregate_without_date_range_requires_clarification(client):
    """
    Aggregate queries without an explicit date range are ambiguous
    and must request clarification instead of executing.
    """
    response = client.post(
        "/process",
        json={
            "text": "How much did I spend on travel?",
            "user_id": "u1",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["type"] == "query"

    data = body["data"]

    # No execution happened
    assert data.get("output") is None

    # Clarification was issued
    assert "context" in data
    assert data["context"].get("commit_decision") == "clarify"
    assert data["context"].get("reason") == "missing_date_range"


def test_aggregate_without_date_range_is_not_an_error(client):
    """
    Clarification is a valid response, not an error condition.
    """
    response = client.post(
        "/process",
        json={
            "text": "How much did I spend on flights?",
            "user_id": "u1",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["type"] == "query"
    assert "error" not in body


def test_clarification_response_shape_is_stable(client):
    """
    Even when execution is blocked, the response envelope
    must remain stable and predictable.
    """
    response = client.post(
        "/process",
        json={
            "text": "How much did I spend on entertainment?",
            "user_id": "u1",
        },
    )

    body = response.json()
    data = body["data"]

    assert "answer" in data
    assert isinstance(data["answer"], str)

    # Explicitly no output when clarification is required
    assert data.get("output") is None

    assert "context" in data
    assert data["context"]["commit_decision"] == "clarify"
