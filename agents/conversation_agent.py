from pydantic_ai import Agent
from pydantic import BaseModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from configurations.config import GOOGLE_API_KEY
from configurations.config import GEMINI_MODEL_NAME
# Provider & Model setup
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel(GEMINI_MODEL_NAME, provider=provider)

class ConversationResponse(BaseModel):
    response: str
    conversation_type: str  # "general", "expense_help", "greeting"

# Simple conversation agent
conversation_agent = Agent(
    model,
    system_prompt=(
        "You are a friendly AI assistant for an expense chatbot. "
        "Help users with general questions, provide guidance on expense tracking, "
        "and have casual conversations.\n\n"
        
        "Be helpful, friendly, and brief. If users ask about expense features, "
        "guide them to try logging expenses or asking about their spending.\n\n"
        
        "Classify conversation as:\n"
        "- 'greeting': Hello, hi, how are you\n"
        "- 'expense_help': Questions about expense features\n"
        "- 'general': Other conversation\n"
    ),
    output_type=ConversationResponse
)

async def handle_conversation(user_input: str, user_id: str) -> ConversationResponse:
    """Simple conversation handler - just like your other agents"""
    result = await conversation_agent.run(user_input)
    return result.output