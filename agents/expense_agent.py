import json
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from models.expense import Expenses
from config import GOOGLE_API_KEY
from datetime import datetime

# -----------------------------
# Expense Extraction Agent
# -----------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel("gemini-1.5-flash", provider=provider)

expense_agent = Agent(
    model,
    system_prompt=(
        "You are an assistant that extracts structured expense data from user messages. "
        "Return JSON strictly matching this schema:\n"
        "{'amount': float, 'date': str, 'companions': list[str], 'description': str, "
        "'category': str, 'subcategory': str, 'paymentMethod': str}\n"
        "Return only JSON. Do not include extra text or explanations."
    ),
    output_type=Expenses
)

# -----------------------------
# Message Generation Agent
# -----------------------------
message_agent = Agent(
    model,
    system_prompt="""You are a cheerful, human-like assistant. You will receive a JSON object containing an expense with these fields:
    - amount (float): the expense amount
    - date (string or datetime): the date of the expense
    - companions (list of strings): people involved
    - description (string): what the expense was for
    - category (string): the main category
    - subcategory (string): the subcategory
    Your task is to create a fun, human-friendly recap message. The style should be:
    - Start with something like: “You had a great day! 🎉”
    - Then list the expense info naturally (who, what, when, amount)
    - Include companions and category/subcategory in a natural way
    - Sprinkle in cheerful emojis (food, money, celebration, etc.)
    - End with a positive or fun closing remark
    - Do not ask for JSON or input; just generate the message""",
    output_type=str
)

# -----------------------------
# Expense Parsing Function
# -----------------------------
async def generate_expense_message(expense: Expenses) -> str:
    """
    Forward the expense JSON to message_agent to generate a friendly message.
    """
    # Convert Pydantic model to dict
    expense_dict = expense.model_dump()  # or expense.dict() if using Pydantic <2

    # Convert datetime to ISO string for JSON serialization
    if isinstance(expense_dict.get("date"), (datetime,)):
        expense_dict["date"] = expense_dict["date"].isoformat()

    # Serialize to JSON string
    expense_json_str = json.dumps(expense_dict)

    # Run the message agent with JSON string
    user_message: str = await message_agent.run(expense_json_str)
    return user_message

# -----------------------------
# Unified Expense Handling
# -----------------------------
async def parse_and_generate_message(user_input: str) -> dict:
    """
    Parse user input to structured expense JSON and generate user-friendly message.
    Returns a dict with both.
    """
    # Extract structured JSON
    result = await expense_agent.run(user_input)
    expense_data: Expenses = result.output  # ✅ Get actual Expenses model from AgentRunResult

    # Generate natural message
    user_message: str = await generate_expense_message(expense_data)

    return {
        "expense_data": expense_data,
        "user_message": user_message
    }
