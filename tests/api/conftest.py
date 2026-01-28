import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from API_LAYER.app import app

@pytest.fixture(scope="session")
def client():
    # API tests must NOT hit real DB
    app.state.db = MagicMock()
    return TestClient(app)
