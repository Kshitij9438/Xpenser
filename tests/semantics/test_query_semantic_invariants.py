def test_reject_list_and_aggregate_together(client):
    response = client.post(
        "/process",
        json={
            "text": "Show my expenses and how much I spent",
            "user_id": "u1",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY_SHAPE"

def test_reject_group_by_without_aggregate(client):
    response = client.post(
        "/process",
        json={
            "text": "Show expenses grouped by category",
            "user_id": "u1",
        },
    )

    assert response.status_code == 400
    assert "group_by requires aggregate" in response.json()["error"]["message"]

def test_reject_aggregate_with_columns(client):
    response = client.post(
        "/process",
        json={
            "text": "How much did I spend, show category and date",
            "user_id": "u1",
        },
    )

    assert response.status_code == 400
def test_valid_simple_aggregate_still_works(client):
    response = client.post(
        "/process",
        json={
            "text": "How much did I spend on food?",
            "user_id": "u1",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["query"]["shape"] == "aggregate"
