

import asyncio
import logging
from prisma import Prisma
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

async def diagnose_database():
    """Diagnose what's actually in the database for this user."""
    user_id = "22f8e821-16ea-4f98-a945-30f0e20181f5"
    
    # Connect to database
    db = Prisma()
    await db.connect()
    
    try:
        print(f"🔍 Diagnosing database for user: {user_id}")
        print("=" * 60)
        
        # 1. Check total expenses for this user
        total_count = await db.expense.count(where={"user_id": user_id})
        print(f" Total expenses for user: {total_count}")
        
        if total_count == 0:
            print("❌ No expenses found for this user ID")
            return
        
        # 2. Get sample expenses to see the data structure
        sample_expenses = await db.expense.find_many(
            where={"user_id": user_id},
            take=5,
            order={"createdAt": "desc"}
        )
        
        print(f"\n📋 Sample expenses (showing {len(sample_expenses)}):")
        for i, expense in enumerate(sample_expenses, 1):
            print(f"\n{i}. ID: {expense.id}")
            print(f"   Amount: {expense.amount}")
            print(f"   Category: {expense.category}")
            print(f"   Date: {expense.date}")
            print(f"   Payment Method: {expense.paymentMethod}")
            print(f"   Description: {expense.description}")
            print(f"   Companions: {expense.companions}")
        
        # 3. Check unique payment methods
        all_expenses = await db.expense.find_many(where={"user_id": user_id})
        payment_methods = set()
        for expense in all_expenses:
            if expense.paymentMethod:
                payment_methods.add(expense.paymentMethod)
        
        print(f"\n💳 Unique payment methods found:")
        for method in sorted(payment_methods):
            print(f"   - '{method}'")
        
        # 4. Check date formats
        dates = set()
        for expense in all_expenses:
            dates.add(expense.date.strftime("%Y-%m-%d"))
        
        print(f"\n📅 Date range in database:")
        sorted_dates = sorted(dates)
        if sorted_dates:
            print(f"   From: {sorted_dates[0]}")
            print(f"   To: {sorted_dates[-1]}")
            print(f"   Total unique dates: {len(sorted_dates)}")
        
        # 5. Check for expenses around April 8, 2025
        april_expenses = await db.expense.find_many(
            where={
                "user_id": user_id,
                "date": {
                    "gte": datetime(2025, 4, 1),
                    "lte": datetime(2025, 4, 30)
                }
            }
        )
        
        print(f"\n️ Expenses in April 2025: {len(april_expenses)}")
        for expense in april_expenses:
            print(f"   - {expense.date.strftime('%Y-%m-%d')}: ${expense.amount} ({expense.paymentMethod}) - {expense.description}")
        
        # 6. Check for any expenses with "bank" or "netbanking" in payment method
        bank_expenses = await db.expense.find_many(
            where={
                "user_id": user_id,
                "paymentMethod": {
                    "contains": "bank"
                }
            }
        )
        
        print(f"\n🏦 Expenses with 'bank' in payment method: {len(bank_expenses)}")
        for expense in bank_expenses:
            print(f"   - {expense.date.strftime('%Y-%m-%d')}: ${expense.amount} ({expense.paymentMethod}) - {expense.description}")
        
        # 7. Check for expenses with "netbanking" specifically
        netbanking_expenses = await db.expense.find_many(
            where={
                "user_id": user_id,
                "paymentMethod": {
                    "contains": "netbanking"
                }
            }
        )
        
        print(f"\n Expenses with 'netbanking' in payment method: {len(netbanking_expenses)}")
        for expense in netbanking_expenses:
            print(f"   - {expense.date.strftime('%Y-%m-%d')}: ${expense.amount} ({expense.paymentMethod}) - {expense.description}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Full error details:")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(diagnose_database())
