# services/router.py

from agents.router_agent import router_agent

async def get_route(user_input: str):
    """
    Uses the Router Agent to classify a user input into route 1, 2, or 3.
    Returns the structured output object (with .route).
    """
    result = await router_agent.run(user_input)
    return result.output  # Should already have a .route field
