# app.py
import logging
import json
from typing import Any, Dict
from asyncio import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from configurations.config import DATABASE_URL
from services.router import get_route
from prisma import Prisma

from core.intent import Intent
from executors.expense import ExpenseExecutor
from executors.query import QueryExecutor
from executors.conversation import ConversationExecutor


# -----------------------------
# Route → Intent mapping
# -----------------------------
ROUTE_TO_INTENT = {
    1: "expense",
    2: "query",
    3: "conversation",
}


# -----------------------------
# Logging
# -----------------------------
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "time": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "exception": record.exc_text,
            }
        )


logger = logging.getLogger("expense_chatbot_api")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
if not logger.handlers:
    logger.addHandler(handler)


# -----------------------------
# FastAPI
# -----------------------------
app = FastAPI(title="Expense Chatbot API", version="2.0")


# -----------------------------
# Prisma (SINGLE CLIENT)
# -----------------------------
db = Prisma()

DB_CONNECTED = False
DB_ERROR: str | None = None


# -----------------------------
# Executors
# -----------------------------
expense_executor: ExpenseExecutor | None = None
query_executor: QueryExecutor | None = None
conversation_executor: ConversationExecutor | None = None


# -----------------------------
# Metrics
# -----------------------------
metrics_lock = Lock()
request_counters = {
    "expense": 0,
    "query": 0,
    "unknown": 0,
    "total": 0,
    "errors": 0,
}


# -----------------------------
# Models
# -----------------------------
class UserRequest(BaseModel):
    text: str
    user_id: str


# -----------------------------
# Startup / Shutdown
# -----------------------------
@app.on_event("startup")
async def startup():
    """
    IMPORTANT:
    - Prisma MUST connect here (once)
    - Never connect inside request flow
    """
    global expense_executor, query_executor, conversation_executor
    global DB_CONNECTED, DB_ERROR

    expense_executor = ExpenseExecutor()
    query_executor = QueryExecutor(db)
    conversation_executor = ConversationExecutor()

    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set; DB disabled")
        DB_CONNECTED = False
        DB_ERROR = "DATABASE_URL not set"
        return

    try:
        await db.connect()
        DB_CONNECTED = True
        DB_ERROR = None
        logger.info("✅ Prisma DB connected at startup")
    except Exception as e:
        DB_CONNECTED = False
        DB_ERROR = str(e)
        logger.exception("❌ Prisma DB connection failed at startup")


@app.on_event("shutdown")
async def shutdown():
    global DB_CONNECTED
    if db.is_connected():
        await db.disconnect()
        DB_CONNECTED = False
        logger.info("✅ Prisma DB disconnected")


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
async def root():
    return {"message": "Expense Chatbot API is running."}


@app.get("/health")
async def health() -> Dict[str, Any]:
    payload = {
        "status": "ok" if DB_CONNECTED else "degraded",
        "db_connected": DB_CONNECTED,
    }
    if DB_ERROR:
        payload["db_error"] = DB_ERROR
    return payload


@app.get("/metrics")
async def metrics() -> Dict[str, Any]:
    async with metrics_lock:
        return request_counters.copy()


@app.post("/process")
async def process_request(request: UserRequest):
    async with metrics_lock:
        request_counters["total"] += 1

    try:
        logger.info(
            f"[REQUEST_START] user_id={request.user_id}, text_length={len(request.text)}"
        )

        route_result = await get_route(request.text)
        route = route_result.route

        intent = Intent(
            user_id=request.user_id,
            raw_input=request.text,
            type=ROUTE_TO_INTENT.get(route, "conversation"),
        )

        logger.info(
            f"[INTENT] user_id={intent.user_id}, type={intent.type}"
        )

        if intent.type == "expense":
            async with metrics_lock:
                request_counters["expense"] += 1
            return await expense_executor.execute(intent)

        elif intent.type == "query":
            if not DB_CONNECTED:
                raise HTTPException(
                    status_code=503,
                    detail="Database unavailable",
                )

            async with metrics_lock:
                request_counters["query"] += 1

            return await query_executor.execute(intent)

        else:
            async with metrics_lock:
                request_counters["unknown"] += 1
            return await conversation_executor.execute(intent)

    except HTTPException as e:
        async with metrics_lock:
            request_counters["errors"] += 1

        logger.warning(
            f"[HTTP_ERROR] user_id={request.user_id}, status={e.status_code}"
        )

        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "type": "http_error",
                    "message": e.detail,
                }
            },
        )

    except Exception as e:
        async with metrics_lock:
            request_counters["errors"] += 1

        logger.exception(f"[UNHANDLED_ERROR] {type(e).__name__}: {e}")

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "unexpected_error",
                    "message": "An unexpected error occurred",
                }
            },
        )


# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    import uvicorn
    import os

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        workers=1,
    )
