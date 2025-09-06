# FILE: test_query_builder.py
import asyncio
from prisma import Prisma
from models.query import QueryRequest, QueryFilters, DateRange
from services.query_builder import run_query

async def main():
    # -----------------------------
    # Connect Prisma
    # -----------------------------
    prisma_db = Prisma()
    await prisma_db.connect()
    print("✅ Prisma connected")

    # -----------------------------
    # Example QueryRequest (simulate parsed query)
    # -----------------------------
    request = QueryRequest(
        user_id="22f8e821-16ea-4f98-a945-30f0e20181f5",
        filters=QueryFilters(
            category=None,
            subcategory=None,
            companions=None,
            paymentMethod=None,
            min_amount=None,
            max_amount=None,
            date_range=None,
            extras=None
        ),
        aggregate="sum",           # Test numeric aggregation
        aggregate_field="amount",
        group_by=None,             # No group_by for this test
        columns=None,
        limit=100,
        offset=0,
        sort_by="date",
        sort_order="desc"
    )

    # -----------------------------
    # Run the query builder
    # -----------------------------
    result = await run_query(prisma_db, request)

    # -----------------------------
    # Inspect the output
    # -----------------------------
    print("QueryResult object:", result)
    if hasattr(result, "__dict__"):
        print("QueryResult attributes:", result.__dict__)

    # -----------------------------
    # Disconnect Prisma
    # -----------------------------
    await prisma_db.disconnect()
    print("✅ Prisma disconnected")

if __name__ == "__main__":
    asyncio.run(main())
