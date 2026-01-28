from asyncio import wait_for, TimeoutError
from fastapi import HTTPException

from core.intent import Intent
from executors.base import BaseExecutor
from services.query_orchestrator import handle_user_query
from services.utils import deep_serialize


class QueryExecutor(BaseExecutor):
    """
    Executes query-related intents.
    Logic extracted directly from app.py without behavior changes.
    """

    def __init__(self, db):
        self.db = db

    async def execute(self, intent: Intent) -> dict:
        try:
            try:
                final_answer = await wait_for(
                    handle_user_query(intent.raw_input, intent.user_id, self.db),
                    timeout=45,
                )
            except TimeoutError:
                raise HTTPException(
                    status_code=504,
                    detail="Query processing timed out",
                )

            data = deep_serialize(final_answer)

            # -----------------------------
            # ZERO-DATA NORMALIZATION (FIX)
            # -----------------------------
            output = data.get("output")

            if output is None:
                output = {
                    "rows": [],
                    "aggregate_result": {"sum": 0},
                }
            else:
                output.setdefault("rows", [])
                output.setdefault("aggregate_result", {"sum": 0})

            data["output"] = output

            return {
                "type": "query",
                "data": data,
                "message": getattr(final_answer, "answer", ""),
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=str(e),
            )
