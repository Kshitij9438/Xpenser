import os
import pytest
from fastapi.testclient import TestClient
from prisma import Prisma

from API_LAYER.app import app
from tests.integration.safety_check import assert_test_db


@pytest.fixture(scope="session")
def client():
    # Absolute safety check
    assert_test_db()

    # Explicitly mark test mode
    os.environ["XPENSER_TEST_MODE"] = "1"

    # OWN the DB for integration tests
    db = Prisma()
    app.state.db = db

    with TestClient(app) as client:
        yield client

    os.environ.pop("XPENSER_TEST_MODE", None)
