import asyncio
import pytest

from services.router import get_route


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

async def _route(text: str) -> int:
    result = await get_route(text)
    return result.route


# ---------------------------------------------------------------------
# QUERY-SAFETY TESTS (TEST MODE ENABLED)
# These must NOT call the LLM and must NEVER create expenses.
# ---------------------------------------------------------------------

@pytest.fixture
def query_mode(monkeypatch):
    monkeypatch.setenv("XPENSER_TEST_MODE", "1")
    yield
    monkeypatch.delenv("XPENSER_TEST_MODE", raising=False)


def test_grouping_language_routes_to_query(query_mode):
    route = asyncio.run(
        _route("Group my expenses by category")
    )
    assert route == 2


def test_breakdown_language_routes_to_query(query_mode):
    route = asyncio.run(
        _route("Give me a breakdown of my expenses")
    )
    assert route == 2


def test_numeric_aggregate_routes_to_query(query_mode):
    route = asyncio.run(
        _route("How much did I spend last month?")
    )
    assert route == 2


def test_list_language_routes_to_query(query_mode):
    route = asyncio.run(
        _route("Show my travel expenses")
    )
    assert route == 2


def test_word_expense_alone_does_not_imply_creation(query_mode):
    """
    The word 'expense' alone must NOT trigger creation.
    """
    route = asyncio.run(
        _route("Show my expenses")
    )
    assert route == 2


def test_group_and_expense_combination_routes_to_query(query_mode):
    """
    Past failure case:
    'Group my expenses by category' must be query.
    """
    route = asyncio.run(
        _route("Group my expenses by category")
    )
    assert route == 2


def test_ambiguous_text_defaults_to_query(query_mode):
    """
    Ambiguous or vague text should never create expenses.
    """
    route = asyncio.run(
        _route("Expenses")
    )
    assert route == 2


# ---------------------------------------------------------------------
# EXPENSE CREATION TESTS (TEST MODE DISABLED)
# These must exercise REAL heuristics.
# ---------------------------------------------------------------------

def test_explicit_add_routes_to_expense_creation(monkeypatch):
    monkeypatch.delenv("XPENSER_TEST_MODE", raising=False)

    route = asyncio.run(
        _route("Add a food expense of 500 rupees")
    )
    assert route == 1


def test_paid_routes_to_expense_creation(monkeypatch):
    monkeypatch.delenv("XPENSER_TEST_MODE", raising=False)

    route = asyncio.run(
        _route("I paid 300 for groceries")
    )
    assert route == 1


def test_bought_routes_to_expense_creation(monkeypatch):
    monkeypatch.delenv("XPENSER_TEST_MODE", raising=False)

    route = asyncio.run(
        _route("Bought coffee for 120")
    )
    assert route == 1
