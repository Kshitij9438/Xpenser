# FILE: debug_query_pipeline.py
import asyncio
import logging
import json
from prisma import Prisma

from services.query_orchestrator import handle_user_query
from agents.query_parser import parse_query
from services.query_builder import run_query
from agents.query_answer import answer_query

# Configure logging for deep tracing
logging.basicConfig(
    filename="debug_query_pipeline.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

async def deep_debug_query(user_text: str, user_id: str):
    prisma_db = Prisma()
    try:
        # Connect to Prisma
        await prisma_db.connect()
        logging.info("✅ Connected to Prisma")

        # Step 1: Parse user query
        parsed_request = await parse_query(user_text, user_id)
        logging.info(f"🔹 Parsed QueryRequest: {parsed_request.json() if hasattr(parsed_request,'json') else parsed_request}")

        # Step 2: Build Prisma where clause (internal debug)
        from services.query_builder import _build_where_from_filters
        where_clause = _build_where_from_filters(parsed_request.filters, user_id)
        logging.info(f"🔹 Prisma 'where' clause: {json.dumps(where_clause, default=str)}")

        # Step 3: Run query
        query_result = await run_query(prisma_db, parsed_request)
        logging.info(f"🔹 QueryResult raw: {query_result.json() if hasattr(query_result,'json') else query_result}")

        # Step 4: Answer generation
        nlp_response = await answer_query(user_text, query_result, user_id)
        logging.info(f"🔹 NLPResponse: {nlp_response.json() if hasattr(nlp_response,'json') else nlp_response}")

        print("✅ Full pipeline completed. Check debug_query_pipeline.log for details.")
        return nlp_response

    except Exception as e:
        logging.exception("❌ Error during deep debug pipeline")
        print(f"❌ Error: {e}")
        return None
    finally:
        await prisma_db.disconnect()
        logging.info("✅ Prisma disconnected")

if __name__ == "__main__":
    # Example usage
    user_text = "Show my all expenses"
    user_id = "22f8e821-16ea-4f98-a945-30f0e20181f5"  # replace with a real user_id from your DB
    asyncio.run(deep_debug_query(user_text, user_id))
