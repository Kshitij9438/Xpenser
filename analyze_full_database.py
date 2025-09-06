"""
Comprehensive Database Analysis Script

This script provides a complete analysis of your expense database including:
- All users and their data
- Complete data structure analysis
- Payment methods, categories, and date ranges
- Data quality assessment
- Query testing with real data
"""

import asyncio
import logging
from prisma import Prisma
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json
from typing import Dict, List, Any, Set

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

class DatabaseAnalyzer:
    def __init__(self):
        self.db = Prisma()
        self.analysis_results = {}
    
    async def connect(self):
        """Connect to the database."""
        await self.db.connect()
        print("✅ Connected to database")
    
    async def disconnect(self):
        """Disconnect from the database."""
        await self.db.disconnect()
        print("✅ Disconnected from database")
    
    async def analyze_all_users(self):
        """Analyze all users in the database."""
        print("\n" + "="*80)
        print("👥 USER ANALYSIS")
        print("="*80)
        
        # Get all unique user IDs
        all_expenses = await self.db.expense.find_many()
        user_ids = set(expense.user_id for expense in all_expenses)
        
        print(f"�� Total unique users: {len(user_ids)}")
        
        user_stats = {}
        for user_id in user_ids:
            user_expenses = await self.db.expense.find_many(where={"user_id": user_id})
            
            # Calculate user statistics
            total_amount = sum(float(exp.amount) for exp in user_expenses)
            date_range = {
                "earliest": min(exp.date for exp in user_expenses),
                "latest": max(exp.date for exp in user_expenses)
            }
            
            user_stats[user_id] = {
                "expense_count": len(user_expenses),
                "total_amount": total_amount,
                "date_range": date_range,
                "avg_amount": total_amount / len(user_expenses) if user_expenses else 0
            }
            
            print(f"\n�� User: {user_id}")
            print(f"   📈 Total expenses: {len(user_expenses)}")
            print(f"   💰 Total amount: ${total_amount:,.2f}")
            print(f"   📊 Average expense: ${total_amount/len(user_expenses):,.2f}")
            print(f"   📅 Date range: {date_range['earliest'].strftime('%Y-%m-%d')} to {date_range['latest'].strftime('%Y-%m-%d')}")
        
        self.analysis_results["users"] = user_stats
        return user_stats
    
    async def analyze_payment_methods(self):
        """Analyze all payment methods in the database."""
        print("\n" + "="*80)
        print("💳 PAYMENT METHOD ANALYSIS")
        print("="*80)
        
        all_expenses = await self.db.expense.find_many()
        
        # Count payment methods
        payment_method_counts = Counter()
        payment_method_amounts = defaultdict(float)
        
        for expense in all_expenses:
            method = expense.paymentMethod or "null"
            payment_method_counts[method] += 1
            payment_method_amounts[method] += float(expense.amount)
        
        print(f"📊 Total payment methods found: {len(payment_method_counts)}")
        print("\n💳 Payment method breakdown:")
        
        for method, count in payment_method_counts.most_common():
            total_amount = payment_method_amounts[method]
            avg_amount = total_amount / count if count > 0 else 0
            print(f"   '{method}': {count} expenses, ${total_amount:,.2f} total, ${avg_amount:,.2f} avg")
        
        self.analysis_results["payment_methods"] = {
            "counts": dict(payment_method_counts),
            "amounts": dict(payment_method_amounts)
        }
        return payment_method_counts
    
    async def analyze_categories(self):
        """Analyze all categories in the database."""
        print("\n" + "="*80)
        print("📂 CATEGORY ANALYSIS")
        print("="*80)
        
        all_expenses = await self.db.expense.find_many()
        
        # Count categories
        category_counts = Counter()
        category_amounts = defaultdict(float)
        subcategory_counts = Counter()
        
        for expense in all_expenses:
            category = expense.category or "null"
            subcategory = expense.subcategory or "null"
            
            category_counts[category] += 1
            category_amounts[category] += float(expense.amount)
            subcategory_counts[subcategory] += 1
        
        print(f"📊 Total categories found: {len(category_counts)}")
        print("\n�� Category breakdown:")
        
        for category, count in category_counts.most_common():
            total_amount = category_amounts[category]
            avg_amount = total_amount / count if count > 0 else 0
            print(f"   '{category}': {count} expenses, ${total_amount:,.2f} total, ${avg_amount:,.2f} avg")
        
        print(f"\n📊 Total subcategories found: {len(subcategory_counts)}")
        print("\n📂 Subcategory breakdown:")
        
        for subcategory, count in subcategory_counts.most_common(10):  # Top 10
            print(f"   '{subcategory}': {count} expenses")
        
        self.analysis_results["categories"] = {
            "counts": dict(category_counts),
            "amounts": dict(category_amounts),
            "subcategories": dict(subcategory_counts)
        }
        return category_counts
    
    async def analyze_date_ranges(self):
        """Analyze date ranges and patterns in the database."""
        print("\n" + "="*80)
        print("📅 DATE RANGE ANALYSIS")
        print("="*80)
        
        all_expenses = await self.db.expense.find_many()
        
        if not all_expenses:
            print("❌ No expenses found")
            return
        
        dates = [exp.date for exp in all_expenses]
        earliest = min(dates)
        latest = max(dates)
        
        print(f"�� Overall date range:")
        print(f"   From: {earliest.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   To: {latest.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Span: {(latest - earliest).days} days")
        
        # Monthly breakdown
        monthly_counts = defaultdict(int)
        monthly_amounts = defaultdict(float)
        
        for expense in all_expenses:
            month_key = expense.date.strftime('%Y-%m')
            monthly_counts[month_key] += 1
            monthly_amounts[month_key] += float(expense.amount)
        
        print(f"\n📊 Monthly breakdown:")
        for month in sorted(monthly_counts.keys()):
            count = monthly_counts[month]
            amount = monthly_amounts[month]
            avg = amount / count if count > 0 else 0
            print(f"   {month}: {count} expenses, ${amount:,.2f} total, ${avg:,.2f} avg")
        
        # Check for specific dates mentioned in the failing query
        april_2025_expenses = await self.db.expense.find_many(
            where={
                "date": {
                    "gte": datetime(2025, 4, 1),
                    "lte": datetime(2025, 4, 30)
                }
            }
        )
        
        print(f"\n🔍 April 2025 expenses: {len(april_2025_expenses)}")
        for expense in april_2025_expenses:
            print(f"   {expense.date.strftime('%Y-%m-%d')}: ${expense.amount} ({expense.paymentMethod}) - {expense.description} - User: {expense.user_id}")
        
        self.analysis_results["date_ranges"] = {
            "earliest": earliest.isoformat(),
            "latest": latest.isoformat(),
            "monthly_counts": dict(monthly_counts),
            "monthly_amounts": dict(monthly_amounts)
        }
    
    async def analyze_companions(self):
        """Analyze companion data."""
        print("\n" + "="*80)
        print("�� COMPANION ANALYSIS")
        print("="*80)
        
        all_expenses = await self.db.expense.find_many()
        
        companion_counts = Counter()
        expenses_with_companions = 0
        
        for expense in all_expenses:
            if expense.companions:
                expenses_with_companions += 1
                for companion in expense.companions:
                    companion_counts[companion] += 1
        
        print(f"📊 Expenses with companions: {expenses_with_companions}")
        print(f"📊 Total unique companions: {len(companion_counts)}")
        
        if companion_counts:
            print("\n👥 Most frequent companions:")
            for companion, count in companion_counts.most_common(10):
                print(f"   '{companion}': {count} times")
        
        self.analysis_results["companions"] = {
            "counts": dict(companion_counts),
            "expenses_with_companions": expenses_with_companions
        }
    
    async def test_specific_queries(self):
        """Test the specific queries that were failing."""
        print("\n" + "="*80)
        print("🧪 QUERY TESTING")
        print("="*80)
        
        # Test the failing query: netbanking on April 8, 2025
        test_user_id = "22f8e821-16ea-4f98-a945-30f0e20181f5"
        
        print(f"🔍 Testing queries for user: {test_user_id}")
        
        # Test 1: All expenses for this user
        user_expenses = await self.db.expense.find_many(where={"user_id": test_user_id})
        print(f"\n1️⃣ Total expenses for user: {len(user_expenses)}")
        
        if user_expenses:
            # Test 2: Netbanking expenses
            netbanking_expenses = await self.db.expense.find_many(
                where={
                    "user_id": test_user_id,
                    "paymentMethod": {"equals": "netbanking", "mode": "insensitive"}
                }
            )
            print(f"2️⃣ Netbanking expenses: {len(netbanking_expenses)}")
            
            # Test 3: April 2025 expenses
            april_expenses = await self.db.expense.find_many(
                where={
                    "user_id": test_user_id,
                    "date": {
                        "gte": datetime(2025, 4, 1),
                        "lte": datetime(2025, 4, 30)
                    }
                }
            )
            print(f"3️⃣ April 2025 expenses: {len(april_expenses)}")
            
            # Test 4: Netbanking + April 8, 2025
            specific_expenses = await self.db.expense.find_many(
                where={
                    "user_id": test_user_id,
                    "paymentMethod": {"equals": "netbanking", "mode": "insensitive"},
                    "date": {
                        "gte": datetime(2025, 4, 8),
                        "lte": datetime(2025, 4, 8)
                    }
                }
            )
            print(f"4️⃣ Netbanking on April 8, 2025: {len(specific_expenses)}")
            
            if specific_expenses:
                for expense in specific_expenses:
                    print(f"   ✅ Found: ${expense.amount} - {expense.description}")
            else:
                print("   ❌ No expenses found for this specific query")
                
                # Let's see what payment methods exist for this user
                user_payment_methods = set()
                for exp in user_expenses:
                    if exp.paymentMethod:
                        user_payment_methods.add(exp.paymentMethod)
                
                print(f"   💳 Available payment methods for this user: {list(user_payment_methods)}")
                
                # Let's see what dates exist for this user
                user_dates = set()
                for exp in user_expenses:
                    user_dates.add(exp.date.strftime('%Y-%m-%d'))
                
                print(f"   📅 Available dates for this user: {sorted(list(user_dates))}")
    
    async def generate_data_quality_report(self):
        """Generate a data quality report."""
        print("\n" + "="*80)
        print("📋 DATA QUALITY REPORT")
        print("="*80)
        
        all_expenses = await self.db.expense.find_many()
        
        if not all_expenses:
            print("❌ No data found")
            return
        
        total_expenses = len(all_expenses)
        
        # Check for missing data
        missing_payment_method = sum(1 for exp in all_expenses if not exp.paymentMethod)
        missing_description = sum(1 for exp in all_expenses if not exp.description)
        missing_subcategory = sum(1 for exp in all_expenses if not exp.subcategory)
        empty_companions = sum(1 for exp in all_expenses if not exp.companions)
        
        print(f"📊 Data Quality Metrics:")
        print(f"   Total expenses: {total_expenses}")
        print(f"   Missing payment method: {missing_payment_method} ({missing_payment_method/total_expenses*100:.1f}%)")
        print(f"   Missing description: {missing_description} ({missing_description/total_expenses*100:.1f}%)")
        print(f"   Missing subcategory: {missing_subcategory} ({missing_subcategory/total_expenses*100:.1f}%)")
        print(f"   Empty companions: {empty_companions} ({empty_companions/total_expenses*100:.1f}%)")
        
        # Check for data inconsistencies
        print(f"\n🔍 Data Consistency Checks:")
        
        # Check for negative amounts
        negative_amounts = sum(1 for exp in all_expenses if float(exp.amount) < 0)
        print(f"   Negative amounts: {negative_amounts}")
        
        # Check for very large amounts
        large_amounts = sum(1 for exp in all_expenses if float(exp.amount) > 10000)
        print(f"   Amounts > $10,000: {large_amounts}")
        
        # Check for future dates
        today = datetime.now()
        future_dates = sum(1 for exp in all_expenses if exp.date > today)
        print(f"   Future dates: {future_dates}")
    
    async def save_analysis_to_file(self):
        """Save the complete analysis to a JSON file."""
        filename = f"database_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Convert datetime objects to strings for JSON serialization
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        with open(filename, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=convert_datetime)
        
        print(f"\n�� Analysis saved to: {filename}")
    
    async def run_full_analysis(self):
        """Run the complete database analysis."""
        print("🚀 Starting comprehensive database analysis...")
        print("="*80)
        
        try:
            await self.connect()
            
            # Run all analysis functions
            await self.analyze_all_users()
            await self.analyze_payment_methods()
            await self.analyze_categories()
            await self.analyze_date_ranges()
            await self.analyze_companions()
            await self.test_specific_queries()
            await self.generate_data_quality_report()
            
            # Save results
            await self.save_analysis_to_file()
            
            print("\n" + "="*80)
            print("✅ ANALYSIS COMPLETE!")
            print("="*80)
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            logger.exception("Full error details:")
        finally:
            await self.disconnect()

async def main():
    """Main function to run the database analysis."""
    analyzer = DatabaseAnalyzer()
    await analyzer.run_full_analysis()

if __name__ == "__main__":
    asyncio.run(main())
