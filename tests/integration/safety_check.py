import os

def assert_test_db():
    url = os.getenv("DATABASE_URL", "")
    assert "xpenser_test" in url, (
        "❌ Refusing to run tests against non-test database"
    )
