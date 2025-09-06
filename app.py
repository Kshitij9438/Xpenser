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
from services.date_resolver import resolve_expression, get_today
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
# Utility: Date Replacement
# -----------------------------
def resolve_relative_dates(text: str, date_info: Dict[str, str]) -> str:
    """
    Replace relative date expressions with concrete ISO dates
    """
    if not date_info:
        return text

    replacements = {
        r"\btoday\b": date_info["start_date"],
        r"\byesterday\b": date_info["start_date"],
        r"\bthis week\b": f"{date_info['start_date']} to {date_info['end_date']}",
        r"\blast week\b": f"{date_info['start_date']} to {date_info['end_date']}",
        r"\bthis month\b": f"{date_info['start_date']} to {date_info['end_date']}",
        r"\blast month\b": f"{date_info['start_date']} to {date_info['end_date']}",
    }

    processed = text
    for pattern, replacement in replacements.items():
        processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
    return processed

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
        route_result = await get_route(request.text)
        route = route_result.route
        logger.info(f"[ROUTING] user_id={request.user_id}, route={route}, text='{request.text}'")

        # Resolve relative dates
        date_info = resolve_expression(request.text)
        processed_text = resolve_relative_dates(request.text, date_info)
        if date_info is None:
            today_str = get_today().isoformat()
            date_info = {"start_date": today_str, "end_date": today_str}

        # -----------------
        # Expense Flow
        # -----------------
        if route == 1:
            try:
                # Wrap LLM call with timeout
                try:
                    result = await wait_for(parse_expense(processed_text), timeout=30)
                except TimeoutError:
                    raise HTTPException(status_code=504, detail="Expense parsing timed out")

                expense_data = result.get("expense_data") or {}
                if "date" in expense_data:
                    expense_data["date"] = date_info["start_date"]
                user_message = result.get("user_message")
                expense_json = deep_serialize(expense_data)

                async with metrics_lock:
                    request_counters["expense"] += 1

                logger.info(f"[EXPENSE PARSED] user_id={request.user_id}, expense={expense_json}")
                return {"type": "expense", "data": expense_json, "message": user_message}

            except Exception as e:
                async with metrics_lock:
                    request_counters["errors"] += 1
                logger.exception("[EXPENSE ERROR] user_id=%s", request.user_id)
                raise HTTPException(status_code=500, detail=str(e) if DEBUG else "Expense parsing failed")

        # -----------------
        # Query Flow
        # -----------------
        elif route == 2:
            if not DB_CONNECTED:
                logger.warning("[QUERY BLOCKED] DB not connected; user_id=%s", request.user_id)
                raise HTTPException(status_code=503, detail="Query temporarily unavailable")

            try:
                try:
                    final_answer = await wait_for(
                        handle_user_query(processed_text, request.user_id, db, context={"date_info": date_info}),
                        timeout=45
                    )
                except TimeoutError:
                    raise HTTPException(status_code=504, detail="Query processing timed out")

                answer_data = deep_serialize(final_answer)

                async with metrics_lock:
                    request_counters["query"] += 1

                preview = getattr(final_answer, "answer", "")
                logger.info(f"[QUERY ANSWER] user_id={request.user_id}, preview='{preview[:120]}'")
                return {"type": "query", "data": answer_data, "message": preview}

            except HTTPException:
                raise
            except Exception as e:
                async with metrics_lock:
                    request_counters["errors"] += 1
                logger.exception("[QUERY ERROR] user_id=%s", request.user_id)
                raise HTTPException(status_code=500, detail=str(e) if DEBUG else "Query processing failed")

        # -----------------
        # Unknown Route
        # -----------------
        else:
            async with metrics_lock:
                request_counters["unknown"] += 1
            logger.info(f"[UNKNOWN INPUT] user_id={request.user_id}, text='{request.text}'")
            return {"type": "unknown", "message": "Input does not relate to expenses."}

    except HTTPException:
        raise
    except Exception as e:
        async with metrics_lock:
            request_counters["errors"] += 1
        logger.exception("[GENERAL ERROR] user_id=%s", getattr(request, "user_id", None))
        raise HTTPException(status_code=500, detail=str(e) if DEBUG else "An unexpected error occurred")
