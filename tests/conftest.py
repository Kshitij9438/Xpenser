# tests/conftest.py
import sys
import os
from pathlib import Path

# ---------------------------------------------------------
# Ensure project root is on PYTHONPATH BEFORE app imports
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------
# Now safe to import app + dependencies
# ---------------------------------------------------------
import pytest
from fastapi.testclient import TestClient
from prisma import Prisma
from unittest.mock import MagicMock

from API_LAYER.app import app
from tests.integration.safety_check import assert_test_db


@pytest.fixture(scope="session")
def client(request):
    """
    Unified client fixture for:
    - api tests
    - integration tests
    - semantic tests
    """

    test_path = str(request.node.fspath)

    # ---------------- API TESTS ----------------
    if "/tests/api/" in test_path:
        app.state.db = MagicMock()
        return TestClient(app)

    # ---------------- INTEGRATION + SEMANTICS ----------------
    assert_test_db()
    os.environ["XPENSER_TEST_MODE"] = "1"

    db = Prisma()
    app.state.db = db

    with TestClient(app) as client:
        yield client

    os.environ.pop("XPENSER_TEST_MODE", None)
