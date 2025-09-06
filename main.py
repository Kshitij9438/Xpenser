import asyncio
from services.expense_parser import parse_expense
from services.router import get_route

async def main():
    user_text = "I had a great dinner with Rita yesterday which cost me around 5,600 rupees"
    route_result = await get_route(user_text)
    route = route_result.route
    print("Determined route:", route)

    if route == 1:
        result = await parse_expense(user_text)
        print("Expense JSON for DB:", result["expense_data"].model_dump())
        print("User-friendly message:", result["user_message"])
    else:
        print("Not an expense input.")

if __name__ == "__main__":
    import sys
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
