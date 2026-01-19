from asyncio import wait_for, TimeoutError
from fastapi import HTTPException

from core.intent import Intent
from executors.base import BaseExecutor
from services.expense_parser import parse_expense
from services.utils import deep_serialize


class ExpenseExecutor(BaseExecutor):
    """
    Executes expense-related intents.
    This logic is a direct extraction from app.py with no behavior changes.
    """

    async def execute(self, intent: Intent) -> dict:
        try:
            try:
                result = await wait_for(parse_expense(intent.raw_input), timeout=30)
            except TimeoutError:
                raise HTTPException(status_code=504, detail="Expense parsing timed out")

            expense_data = result.get("expense_data") or {}
            user_message = result.get("user_message")
            expense_json = deep_serialize(expense_data)

            return {
                "type": "expense",
                "data": expense_json,
                "message": user_message,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=str(e),
            )
