from agents.expense_agent import parse_and_generate_message

async def parse_expense(user_input: str):
    """
    Returns a dict containing both structured expense and a user-friendly message.
    """
    result = await parse_and_generate_message(user_input)
    # If result is a dict, extract the Pydantic model from 'expense_data'
    if isinstance(result, dict) and "expense_data" in result:
        return result  # Return the dict as-is
    elif hasattr(result, "output"):
        return result.output
    else:
        return result  # Fallback for unexpected cases
