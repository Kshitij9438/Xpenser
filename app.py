# app.py
import logging
import json
import re
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from asyncio import Lock, wait_for, TimeoutError

from config import DATABASE_URL, DEBUG
from services.expense_parser import parse_expense
from services.router import get_route
from services.query_orchestrator import handle_user_query
from prisma import Prisma
from services.utils import deep_serialize

# -----------------------------
# Structured Logging Setup
# -----------------------------
db = Prisma()

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "exception": record.exc_text,
        }
        return json.dumps(log_record)

logger = logging.getLogger("expense_chatbot_api")
logger.setLevel(logging.INFO)
# Use stdout for container-friendly logging
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(JSONFormatter())
if not logger.handlers:
    logger.addHandler(stream_handler)

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI(title="Expense Chatbot API", version="2.0")

# -----------------------------
# Prisma DB Client
# -----------------------------
DB_CONNECTED: bool = False
DB_ERROR: str | None = None

# Async locks and counters for metrics
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
    except Exception as e:
        DB_CONNECTED = False
        DB_ERROR = str(e)
        logger.exception("❌ Failed to connect Prisma DB")
        if DEBUG:
            raise

@app.on_event("shutdown")
async def shutdown():
    global DB_CONNECTED
    if DB_CONNECTED:
        try:
            await db.disconnect()
            DB_CONNECTED = False
            logger.info("✅ Prisma DB disconnected")
        except Exception as e:
            logger.exception("❌ Failed to disconnect Prisma DB")
    else:
        logger.info("DB not connected; skipping disconnect")

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
    """Returns request counts and error metrics."""
    async with metrics_lock:
        return request_counters.copy()

@app.post("/process")
async def process_request(request: UserRequest):
    global request_counters
    async with metrics_lock:
        request_counters["total"] += 1

    try:
        # Enhanced logging for debugging
        logger.info(f"[REQUEST_START] user_id={request.user_id}, text_length={len(request.text)}")
        
        # Step 1: Route the request
        try:
            route_result = await get_route(request.text)
            route = route_result.route
            logger.info(f"[ROUTING] user_id={request.user_id}, route={route}, text='{request.text[:100]}...'")
        except Exception as e:
            logger.exception(f"[ROUTING_ERROR] user_id={request.user_id}, error={str(e)}")
            raise HTTPException(status_code=500, detail="Failed to route request")

        # -----------------
        # Expense Flow
        # -----------------
        if route == 1:
            try:
                logger.info(f"[EXPENSE_START] user_id={request.user_id}")
                # Wrap LLM call with timeout
                try:
                    result = await wait_for(parse_expense(request.text), timeout=30)
                except TimeoutError:
                    logger.error(f"[EXPENSE_TIMEOUT] user_id={request.user_id}")
                    raise HTTPException(status_code=504, detail="Expense parsing timed out")

                expense_data = result.get("expense_data") or {}
                user_message = result.get("user_message")
                expense_json = deep_serialize(expense_data)

                async with metrics_lock:
                    request_counters["expense"] += 1

                logger.info(f"[EXPENSE_PARSED] user_id={request.user_id}, expense={expense_json}")
                return {"type": "expense", "data": expense_json, "message": user_message}

            except HTTPException:
                raise
            except Exception as e:
                async with metrics_lock:
                    request_counters["errors"] += 1
                logger.exception(f"[EXPENSE_ERROR] user_id={request.user_id}, error={str(e)}")
                raise HTTPException(status_code=500, detail=str(e) if DEBUG else "Expense parsing failed")

        # -----------------
        # Query Flow
        # -----------------
        elif route == 2:
            if not DB_CONNECTED:
                logger.warning(f"[QUERY_BLOCKED] DB not connected; user_id={request.user_id}")
                raise HTTPException(status_code=503, detail="Query temporarily unavailable")

            try:
                logger.info(f"[QUERY_START] user_id={request.user_id}")
                try:
                    final_answer = await wait_for(
                        handle_user_query(request.text, request.user_id, db),
                        timeout=45
                    )
                except TimeoutError:
                    logger.error(f"[QUERY_TIMEOUT] user_id={request.user_id}")
                    raise HTTPException(status_code=504, detail="Query processing timed out")

                answer_data = deep_serialize(final_answer)

                async with metrics_lock:
                    request_counters["query"] += 1

                preview = getattr(final_answer, "answer", "")
                logger.info(f"[QUERY_ANSWER] user_id={request.user_id}, preview='{preview[:120]}'")
                return {"type": "query", "data": answer_data, "message": preview}

            except HTTPException:
                raise
            except Exception as e:
                async with metrics_lock:
                    request_counters["errors"] += 1
                logger.exception(f"[QUERY_ERROR] user_id={request.user_id}, error={str(e)}")
                raise HTTPException(status_code=500, detail=str(e) if DEBUG else "Query processing failed")

        # -----------------
        # Unknown Route
        # -----------------
        else:
            async with metrics_lock:
                request_counters["unknown"] += 1
            logger.info(f"[UNKNOWN_INPUT] user_id={request.user_id}, text='{request.text[:100]}...'")
            return {"type": "unknown", "message": "Input does not relate to expenses."}

    except HTTPException:
        raise
    except Exception as e:
        async with metrics_lock:
            request_counters["errors"] += 1
        logger.exception(f"[GENERAL_ERROR] user_id={getattr(request, 'user_id', None)}, error={str(e)}")
        raise HTTPException(status_code=500, detail=str(e) if DEBUG else "An unexpected error occurred")

import os
import uvicorn

if __name__ == "__main__":
    # Read PORT from environment; default to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, workers=1)
