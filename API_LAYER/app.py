# app.py
import logging
import json
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from asyncio import Lock

from configurations.config import DATABASE_URL, DEBUG
from services.router import get_route
from prisma import Prisma

from core.intent import Intent
from executors.expense import ExpenseExecutor
from executors.query import QueryExecutor
from executors.conversation import ConversationExecutor


# -----------------------------
# Route → Intent mapping (SINGLE SOURCE OF TRUTH)
# -----------------------------
ROUTE_TO_INTENT = {
    1: "expense",
    2: "query",
    3: "conversation",
}

# -----------------------------
# Structured Logging Setup
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
# FastAPI App
# -----------------------------
app = FastAPI(title="Expense Chatbot API", version="2.0")

# -----------------------------
# Prisma + Executors (Lifecycle managed)
# -----------------------------
db = Prisma()

expense_executor: ExpenseExecutor | None = None
query_executor: QueryExecutor | None = None
conversation_executor: ConversationExecutor | None = None

DB_CONNECTED: bool = False
DB_ERROR: str | None = None

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
# Pydantic Models
# -----------------------------
class UserRequest(BaseModel):
    text: str
    user_id: str

# -----------------------------
# Startup / Shutdown Events
# -----------------------------
@app.on_event("startup")
async def startup():
    global DB_CONNECTED, DB_ERROR
    global expense_executor, query_executor, conversation_executor

    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set; DB functionality disabled.")
        DB_CONNECTED = False
        DB_ERROR = "DATABASE_URL not set"
        return

    try:
        await db.connect()
        DB_CONNECTED = True
        DB_ERROR = None
        logger.info("✅ Prisma DB connected")

        # Executors are created ONLY after DB is ready
        expense_executor = ExpenseExecutor()
        query_executor = QueryExecutor(db)
        conversation_executor = ConversationExecutor()

    except Exception:
        DB_CONNECTED = False
        logger.exception("❌ Failed to connect Prisma DB")
        if DEBUG:
            raise


@app.on_event("shutdown")
async def shutdown():
    global DB_CONNECTED
    if DB_CONNECTED:
        await db.disconnect()
        DB_CONNECTED = False
        logger.info("✅ Prisma DB disconnected")

# -----------------------------
# API Endpoints
# -----------------------------
@app.get("/")
async def root():
    return {"message": "Expense Chatbot API is running."}


@app.get("/health")
async def health() -> Dict[str, Any]:
    info = {"status": "ok", "db_connected": DB_CONNECTED}
    if DB_ERROR:
        info["db_error"] = DB_ERROR
    return info


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

        # -----------------
        # Routing
        # -----------------
        route_result = await get_route(request.text)
        route = route_result.route

        # -----------------
        # Intent
        # -----------------
        intent = Intent(
            user_id=request.user_id,
            raw_input=request.text,
            type=ROUTE_TO_INTENT.get(route, "conversation"),
        )

        logger.info(
            f"[INTENT] user_id={intent.user_id}, "
            f"type={intent.type}, text='{intent.raw_input[:100]}...'"
        )

        # -----------------
        # Execution
        # -----------------
        if intent.type == "expense":
            response = await expense_executor.execute(intent)
            async with metrics_lock:
                request_counters["expense"] += 1
            return response

        elif intent.type == "query":
            if not DB_CONNECTED:
                raise HTTPException(status_code=503, detail="Query unavailable")

            response = await query_executor.execute(intent)
            async with metrics_lock:
                request_counters["query"] += 1
            return response

        else:
            response = await conversation_executor.execute(intent)
            async with metrics_lock:
                request_counters["unknown"] += 1
            return response

    except Exception as e:
        async with metrics_lock:
            request_counters["errors"] += 1

        logger.exception(
            f"[ERROR] user_id={request.user_id}, exception={e}"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e) if DEBUG else "An unexpected error occurred",
        )


# -----------------------------
# Entrypoint
# -----------------------------
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, workers=1)
