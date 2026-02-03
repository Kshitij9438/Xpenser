# services/router.py

import os
from types import SimpleNamespace
from typing import Optional

from agents.router_agent import router_agent


# ---------------------------------------------------------------------
# Deterministic Heuristic Router (GUARD, NOT AUTHORITY)
#
# Heuristic precedence (HIGH → LOW):
# 1. Structural analytics (grouping / breakdowns)
# 2. Numeric / analytic queries
# 3. Explicit expense-creation verbs
# ---------------------------------------------------------------------
def _heuristic_route(user_input: str) -> Optional[int]:
    """
    Cheap, deterministic intent guess.
    This is a GUARD, not a source of truth.
    """
    text = user_input.lower()

    # -------------------------------------------------
    # 1. STRUCTURAL ANALYTICS (HIGHEST PRIORITY)
    # -------------------------------------------------
    if any(
        kw in text
        for kw in (
            "group",
            "group by",
            "by category",
            "breakdown",
            "split by",
            "distribution",
        )
    ):
        return 2  # analytics / query route

    # -------------------------------------------------
    # 2. NUMERIC / ANALYTIC QUERIES
    # -------------------------------------------------
    if any(
        kw in text
        for kw in (
            "how much",
            "total",
            "sum",
            "average",
            "avg",
            "count",
            "show",
            "list",
        )
    ):
        return 2  # analytics / query route

    # -------------------------------------------------
    # 3. EXPLICIT EXPENSE CREATION (VERBS ONLY)
    # -------------------------------------------------
    if any(
        kw in text
        for kw in (
            "add",
            "paid",
            "bought",
            "spent on",
        )
    ):
        return 1  # expense creation route

    # -------------------------------------------------
    # Unknown / ambiguous
    # -------------------------------------------------
    return None


# ---------------------------------------------------------------------
# Public API (DROP-IN)
# ---------------------------------------------------------------------
async def get_route(user_input: str):
    """
    Returns an object with `.route`.

    GUARANTEES:
    - LLM is advisory, not authoritative
    - Deterministic guard always exists
    - Disagreements are resolved safely
    """

    # -------------------------------
    # Test mode: deterministic
    # -------------------------------
    if os.getenv("XPENSER_TEST_MODE") == "1":
        return SimpleNamespace(route=2)

    heuristic = _heuristic_route(user_input)

    try:
        llm_result = await router_agent.run(user_input)
        llm_route = getattr(llm_result.output, "route", None)
    except Exception:
        # LLM failure → fallback to heuristic
        if heuristic is not None:
            return SimpleNamespace(route=heuristic)
        raise

    # -------------------------------
    # Guard: disagreement handling
    # -------------------------------
    if heuristic is not None and llm_route is not None:
        if heuristic != llm_route:
            # Deterministic guard wins
            return SimpleNamespace(
                route=heuristic,
                warning="router_disagreement",
                llm_route=llm_route,
            )

    # -------------------------------
    # Normal path
    # -------------------------------
    if llm_route is not None:
        return SimpleNamespace(route=llm_route)

    # -------------------------------
    # Last resort
    # -------------------------------
    if heuristic is not None:
        return SimpleNamespace(route=heuristic)

    raise RuntimeError("Unable to determine route safely")
