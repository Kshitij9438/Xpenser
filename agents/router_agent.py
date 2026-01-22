from pydantic_ai import Agent
from pydantic import BaseModel
from configurations.config import GOOGLE_API_KEY
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from configurations.config import GEMINI_MODEL_NAME

# Provider & Model setup
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel(GEMINI_MODEL_NAME, provider=provider)

# Define router schema
class RouteDecision(BaseModel):
    route: int  # "expense", "query", or "other"

# Router agent
router_agent = Agent(
    model,
    system_prompt=(
    "You are a routing assistant for an expense chatbot. "
    "Decide which agent should handle the user’s message.\n\n"
    "Rules:\n"
    "1. If the user is describing a new expense they made (mentions money spent, bought, paid, etc.), output 1.\n"
    "2. If the user is asking about past expenses, totals, categories, analytics (e.g., 'How much did I spend on food last month?'), output 2.\n"
    "3. If the input is unrelated to expenses, output 3.\n\n"
    "Return strictly as JSON: {\"route\": 1|2|3}."
),
    output_type=RouteDecision
)
