# check_food_expenses_save.py
import asyncio
import csv
import json
from decimal import Decimal
from prisma import Prisma

# Helper to handle Decimals in JSON
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

async def main():
    db = Prisma()
    await db.connect()

    try:
        user_id = '22f8e821-16ea-4f98-a945-30f0e20181f5'
        category = 'health'

        expenses = await db.expense.find_many(
            where={
                'user_id': user_id,
                'category': category
            }
        )

        # Convert results to list of dictionaries
        expenses_list = [
            {
                'id': e.id,
                'amount': float(e.amount) if e.amount is not None else None,
                'category': e.category,
                'subcategory': e.subcategory,
                'date': e.date.isoformat() if e.date else None,
                'paymentMethod': e.paymentMethod,
                'description': e.description,
                'companions': e.companions,
                'createdAt': e.createdAt.isoformat() if e.createdAt else None
            }
            for e in expenses
        ]

        if not expenses_list:
            print(f"No expenses found for user_id={user_id} and category={category}.")
            return

        # Save as JSON
        with open('expenses.json', 'w', encoding='utf-8') as f:
            json.dump(expenses_list, f, ensure_ascii=False, indent=2, default=decimal_default)
        print("Saved results to expenses.json")

        # Save as CSV
        with open('expenses.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=expenses_list[0].keys())
            writer.writeheader()
            writer.writerows(expenses_list)
        print("Saved results to expenses.csv")

    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
