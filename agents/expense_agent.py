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
        "You are an expert expense data extraction assistant. Your job is to carefully analyze user messages and extract accurate, detailed expense information.\n\n"
        "EXTRACTION RULES:\n"
        "1. AMOUNT: Extract the exact monetary value mentioned. Look for numbers with currency symbols, words like 'costing', 'spent', 'paid', etc.\n"
        "2. COMPANIONS: Extract ALL people mentioned who were present during the expense. Look for names, pronouns like 'with [name]', 'me and [name]', etc.\n"
        "3. DESCRIPTION: Create a clear, descriptive summary of what was purchased or what the expense was for. Be specific about items, activities, or services.\n"
        "4. CATEGORY: Choose the most appropriate category from: Food, Shopping, Entertainment, Transport, Health, Bills, Education, Travel, Other\n"
        "5. SUBCATEGORY: Provide a more specific subcategory within the main category (e.g., 'Clothing' for Shopping, 'Restaurant' for Food)\n"
        "6. PAYMENT METHOD: Infer from context if mentioned, otherwise leave as null\n"
        "7. DATE: Use today's date in YYYY-MM-DD format if not specified\n\n"
        "EXAMPLES:\n"
        "Input: 'I went with Reena and Rita on Shopping where I bought items costing about 800'\n"
        "Output: {\n"
        "  'amount': 800.0,\n"
        "  'date': '2025-09-06',\n"
        "  'companions': ['Reena', 'Rita'],\n"
        "  'description': 'Shopping for various items with Reena and Rita',\n"
        "  'category': 'Shopping',\n"
        "  'subcategory': 'General Shopping',\n"
        "  'paymentMethod': null\n"
        "}\n\n"
        "Input: 'Had dinner with John at Pizza Palace, spent $45'\n"
        "Output: {\n"
        "  'amount': 45.0,\n"
        "  'date': '2025-09-06',\n"
        "  'companions': ['John'],\n"
        "  'description': 'Dinner at Pizza Palace with John',\n"
        "  'category': 'Food',\n"
        "  'subcategory': 'Restaurant',\n"
        "  'paymentMethod': null\n"
        "}\n\n"
        "IMPORTANT: Be thorough and accurate. Extract ALL companions mentioned. Create meaningful descriptions. Choose appropriate categories and subcategories. Return ONLY valid JSON."
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
    - Start with something like: "You had a great day! 🎉"
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
    expense_dict = expense.model_dump()

    # Convert datetime to ISO string for JSON serialization
    if isinstance(expense_dict.get("date"), datetime):
        expense_dict["date"] = expense_dict["date"].isoformat()

    # Serialize to JSON string
    expense_json_str = json.dumps(expense_dict)

    # Run the message agent with JSON string
    result = await message_agent.run(expense_json_str)
    
    # Extract just the output string from the agent result
    if hasattr(result, 'output'):
        return result.output
    else:
        return str(result)

# -----------------------------
# Unified Expense Handling
# -----------------------------
async def parse_and_generate_message(user_input: str) -> dict:
    """
    Parse user input to structured expense JSON and generate user-friendly message.
    Returns a dict with both.
    """
    try:
        # Extract structured JSON
        result = await expense_agent.run(user_input)
        expense_data: Expenses = result.output

        # Generate natural message
        user_message: str = await generate_expense_message(expense_data)

        return {
            "expense_data": expense_data,
            "user_message": user_message
        }
    except Exception as e:
        # Fallback: create a basic expense structure
        from datetime import datetime
        fallback_expense = Expenses(
            amount=0.0,
            date=datetime.now(),
            companions=[],
            description=user_input,
            category="Other",
            subcategory="Unknown",
            paymentMethod=None
        )
        
        return {
            "expense_data": fallback_expense,
            "user_message": f"I had trouble parsing that expense: {user_input}. Please try rephrasing it."
        }
