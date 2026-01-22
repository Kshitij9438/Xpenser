import asyncio
import logging
from services.query_orchestrator import handle_user_query
from prisma import Prisma

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

async def debug_query():
    # Test the exact query that's failing
    user_text = "how much have I spent through netbanking on 8th of April 2025"
    user_id = "22f8e821-16ea-4f98-a945-30f0e20181f5"
    
    # Connect to database
    db = Prisma()
    await db.connect()
    
    try:
        print(f"Testing query: {user_text}")
        print(f"User ID: {user_id}")
        
        # Test date resolution
        from services.date_resolver import resolve_expression
        date_info = resolve_expression(user_text)
        print(f"Date resolution: {date_info}")
        
        # Test the full query
        result = await handle_user_query(user_text, user_id, db)
        print(f"Query result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Full error details:")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_query())
