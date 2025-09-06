# FILE: check_expenses.py
import asyncio
from collections import defaultdict
from prisma import Prisma


# Optional: keep your test user_id for deeper inspection
TEST_USER_ID = "18bc7443-031e-4dd7-b891-d87216fc812d"


async def main():
    db = Prisma()
    await db.connect()

    # Count total expenses first
    total_expenses = await db.expense.count()
    if total_expenses == 0:
        print("⚠️ Database has no expenses at all.")
        await db.disconnect()
        return

    print(f"✅ Database has {total_expenses} expenses total.\n")

    # Fetch all expenses (just user_id and maybe category/amount for reference)
    all_rows = await db.expense.find_many()

    # Group by user_id
    grouped = defaultdict(list)
    for r in all_rows:
        grouped[r.user_id].append(r)

    print("📊 Expenses per user_id:")
    for uid, items in grouped.items():
        print(f"- {uid} → {len(items)} expenses")

    # Optional: deep dive into your test user
    if TEST_USER_ID:
        print(f"\n🔍 Details for TEST_USER_ID={TEST_USER_ID}:")
        if TEST_USER_ID not in grouped:
            print("⚠️ No expenses found for this user.")
        else:
            for r in grouped[TEST_USER_ID]:
                print(f"  - {r.date.date()} | {r.category} | {r.amount}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
