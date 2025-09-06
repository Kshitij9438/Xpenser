# FILE: db_data_puller.py

import asyncio
from prisma import Prisma
from datetime import datetime, timezone
from models.query import QueryResult

# -----------------------------
# Initialize Prisma client
# -----------------------------
db = Prisma()

# -----------------------------
# Fetch all expense rows for a user
# -----------------------------
async def fetch_all_user_expenses(user_id: str):
    await db.connect()
    try:
        rows = await db.expense.find_many(
            where={"user_id": user_id},
            order={"date": "desc"}  # newest first
        )

        result = []
        for r in rows:
            result.append({
                "id": r.id,
                "user_id": r.user_id,
                "amount": float(r.amount),
                "category": r.category,
                "subcategory": r.subcategory,
                "date": r.date.isoformat(),
                "paymentMethod": r.paymentMethod,
                "description": r.description,
                "createdAt": r.createdAt.isoformat(),
                "companions": r.companions if r.companions else []
            })
        return result
    finally:
        await db.disconnect()


# -----------------------------
# Compute aggregates
# -----------------------------
def compute_aggregates(rows):
    amounts = [r["amount"] for r in rows]
    if not amounts:
        return {}
    return {
        "sum": sum(amounts),
        "avg": sum(amounts) / len(amounts),
        "count": len(amounts),
        "min": min(amounts),
        "max": max(amounts)
    }


# -----------------------------
# Build QueryResult
# -----------------------------
async def build_full_query_result(user_id: str) -> QueryResult:
    rows = await fetch_all_user_expenses(user_id)
    aggregates = compute_aggregates(rows)

    # Meta info with timezone-aware datetime
    meta = {"fetched_at": datetime.now(timezone.utc).isoformat(), "row_count": len(rows)}

    return QueryResult(
        rows=rows,
        aggregate_result=aggregates if aggregates else None,
        meta=meta
    )


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    async def main():
        user_id = "22f8e821-16ea-4f98-a945-30f0e20181f5"
        result = await build_full_query_result(user_id)

        # Pydantic v2: use model_dump_json for JSON output
        print(result.model_dump_json(indent=2))

    asyncio.run(main())
