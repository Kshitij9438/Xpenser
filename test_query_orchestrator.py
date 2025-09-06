# debug_query_orchestrator.py
import asyncio
from prisma import Prisma
from services.query_orchestrator import handle_user_query

# Test inputs
test_inputs = [
    {
        "user_prompt": "Show me my food expenses in this month",
        "user_id": "22f8e821-16ea-4f98-a945-30f0e20181f5"
    }
]

async def run_debug():
    prisma_db = Prisma()
    await prisma_db.connect()
    print("✅ Connected to Prisma\n")

    for test in test_inputs:
        user_prompt = test["user_prompt"]
        user_id = test["user_id"]

        print("--- Running Debug Test ---")
        print("User Prompt:", user_prompt)
        print("User ID:", user_id)

        # Step 1: Directly query Prisma
        try:
            expenses = await prisma_db.expenses.find_many(where={"user_id": user_id})
            print("✅ Prisma fetched rows:", len(expenses))
            if len(expenses) > 0:
                print("Sample row:", dict(expenses[0]))
            else:
                print("⚠️ No data found for this user in the database")
        except Exception as e:
            print("❌ Prisma query failed:", e)

        # Step 2: Run orchestrator
        try:
            response = await handle_user_query(user_prompt, user_id, prisma_db)
            print("\n✅ Orchestrator response:")
            print(response)
        except Exception as e:
            print("❌ Orchestrator failed:", e)

    await prisma_db.disconnect()
    print("\n✅ Prisma disconnected")

if __name__ == "__main__":
    asyncio.run(run_debug())
