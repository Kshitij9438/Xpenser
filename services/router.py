# services/router.py

from agents.router_agent import router_agent
import os
from types import SimpleNamespace

async def get_route(user_input: str):
    """
    Uses the Router Agent to classify a user input into route 1, 2, or 3.
    Returns the structured output object (with .route).
    """
    if os.getenv("XPENSER_TEST_MODE") == "1":
        return SimpleNamespace(route=2)
    result = await router_agent.run(user_input)
    return result.output  # Should already have a .route field


