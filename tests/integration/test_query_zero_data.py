import pytest


def test_zero_data_aggregate_returns_zero(client):
    response = client.post(
        "/process",
        json={
            "text": "How much did I spend on travel?",
            "user_id": "u1",
        },
    )

    body = response.json()
    assert body["type"] == "query"

    output = body["data"]["output"]
    assert output["rows"] == []
    assert output["aggregate_result"]["sum"] == 0


def test_zero_data_is_not_error(client):
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


def test_zero_data_output_shape_is_stable(client):
    response = client.post(
        "/process",
        json={
            "text": "How much did I spend on entertainment?",
            "user_id": "u1",
        },
    )

    output = response.json()["data"]["output"]
    assert "rows" in output
    assert "aggregate_result" in output
    assert isinstance(output["rows"], list)
