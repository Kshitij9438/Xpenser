import asyncio
from prisma import Prisma
from datetime import datetime
from decimal import Decimal

USER_ID = "22f8e821-16ea-4f98-a945-30f0e20181f5"

async def main():
    db = Prisma()
    await db.connect()

    # Ensure user exists (important)
    await db.user.upsert(
        where={"id": USER_ID},
        data={
            "create": {
                "id": USER_ID,
                "email": "test@example.com",
            },
            "update": {},
        },
    )

    # Insert expense
    await db.expense.create(
        data={
            "id": "exp_test_1",
            "amount": Decimal("200.00"),
            "category": "Food",
            "subcategory": "Lunch",
            "date": datetime.utcnow(),
            "paymentMethod": "Cash",
            "description": "Test lunch expense",
            "companions": [],
            "user_id": USER_ID,
        }
    )

    await db.disconnect()
    print("✅ Test expense inserted")

asyncio.run(main())
