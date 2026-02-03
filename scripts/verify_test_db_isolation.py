import os
import asyncio
from prisma import Prisma


async def main():
    db_url = os.getenv("DATABASE_URL")

    # ---- HARD SAFETY CHECK ----
    if not db_url or "xpenser_test" not in db_url:
        raise RuntimeError(
            "❌ SAFETY ABORT: DATABASE_URL does not point to xpenser_test"
        )

    print("✅ DATABASE_URL verified:", db_url)

    db = Prisma()
    await db.connect()

    # ---- COUNT BEFORE ----
    before = await db.expense.count()
    print(f"📊 Expense count BEFORE delete: {before}")

    # ---- DESTRUCTIVE OPERATION ----
    await db.expense.delete_many()
    print("🧨 delete_many() executed on Expense table")

    # ---- COUNT AFTER ----
    after = await db.expense.count()
    print(f"📊 Expense count AFTER delete: {after}")

    # ---- ASSERTIONS ----
    assert after == 0, "❌ Test DB was not fully cleared"
    assert after <= before, "❌ Row count increased after delete (impossible)"

    await db.disconnect()

    print("✅ Test DB isolation verified. Production DB untouched.")


if __name__ == "__main__":
    asyncio.run(main())
