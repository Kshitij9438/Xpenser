# FILE: test_query_parser.py
import asyncio
from agents.query_parser import parse_query

async def main():
    user_text = "How much did I spend last month?"
    user_id = "22f8e821-16ea-4f98-a945-30f0e20181f5"

    # Run the parser
    parsed_result = await parse_query(user_text, user_id)

    # Inspect the output
    print("Parsed result object:", parsed_result)
    # If it has attributes like 'intent', 'entities', or 'filters':
    if hasattr(parsed_result, "__dict__"):
        print("Parsed attributes:", parsed_result.__dict__)

if __name__ == "__main__":
    asyncio.run(main())
