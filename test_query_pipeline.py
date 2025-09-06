"""
Test script to verify the improved query pipeline works correctly.
"""

import asyncio
import logging
from services.query_orchestrator import handle_user_query
from prisma import Prisma

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

async def test_query_pipeline():
    """Test the improved query pipeline with the failing query."""
    
    # Test cases based on the database analysis
    test_cases = [
        {
            "query": "how much have I spent through netbanking on 8th of April 2025",
            "user_id": "22f8e821-16ea-4f98-a945-30f0e20181f5",
            "expected": "Should find the $694 netbanking expense on April 8, 2025"
        },
        {
            "query": "show all my entertainment expenses",
            "user_id": "22f8e821-16ea-4f98-a945-30f0e20181f5", 
            "expected": "Should find 13 entertainment expenses"
        },
        {
            "query": "how much did I spend on food last month",
            "user_id": "22f8e821-16ea-4f98-a945-30f0e20181f5",
            "expected": "Should calculate total food spending"
        },
        {
            "query": "list all my netbanking expenses",
            "user_id": "22f8e821-16ea-4f98-a945-30f0e20181f5",
            "expected": "Should find 15 netbanking expenses"
        }
    ]
    
    # Connect to database
    db = Prisma()
    await db.connect()
    
    try:
        print("🧪 Testing Improved Query Pipeline")
        print("=" * 60)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}️⃣ Testing: {test_case['query']}")
            print(f"   Expected: {test_case['expected']}")
            
            try:
                result = await handle_user_query(
                    test_case['query'], 
                    test_case['user_id'], 
                    db
                )
                
                print(f"   ✅ Result: {result.answer}")
                
                if result.output and result.output.rows:
                    print(f"   📊 Found {len(result.output.rows)} expenses")
                    if result.output.aggregate_result:
                        print(f"   �� Aggregate: {result.output.aggregate_result}")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print("\n" + "=" * 60)
        print("✅ Query Pipeline Testing Complete!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.exception("Full error details:")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_query_pipeline())
