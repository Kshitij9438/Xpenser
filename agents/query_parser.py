# FILE: agents/query_parser_improved.py
"""
PHASE 1 CRITICAL FIXES - Enhanced Query Parser
- Fixed Pydantic model safety issues
- Added API rate limiting and resilience
- Enhanced user ID validation
- Improved error handling and fallbacks
- Better canonicalization
"""

import logging
import asyncio
import time
from typing import Any, Dict, Optional, List
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from models.query import QueryRequest, QueryFilters
from config import GOOGLE_API_KEY
from services.preparser import pre_parse
from services.canonicalizer import canonicalize_category

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("query_parser")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("query_parser.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

# -----------------------------
# API Rate Limiting (Critical Fix #1)
# -----------------------------
class APIRateLimiter:
    def __init__(self, max_requests_per_minute: int = 15):
        self.max_requests = max_requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [req_time for req_time in self.requests if now - req_time < 60]
            
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = min(self.requests)
                wait_time = 60 - (now - oldest_request) + 1  # +1 for safety
                logger.warning(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
                # Clean up again after waiting
                now = time.time()
                self.requests = [req_time for req_time in self.requests if now - req_time < 60]
            
            self.requests.append(now)

# Global rate limiter instance
rate_limiter = APIRateLimiter(max_requests_per_minute=15)

def with_rate_limiting(func):
    """Decorator to add rate limiting to API calls"""
    async def wrapper(*args, **kwargs):
        await rate_limiter.acquire()
        return await func(*args, **kwargs)
    return wrapper

# -----------------------------
# User ID Validation (Critical Fix #2)
# -----------------------------
def validate_user_id(user_id: Any) -> str:
    """
    Validate and normalize user_id to ensure it's a proper string
    """
    if user_id is None:
        raise ValueError("User ID cannot be None")
    
    # Convert to string if it's a number
    if isinstance(user_id, (int, float)):
        user_id = str(int(user_id))
    
    # Ensure it's a string
    if not isinstance(user_id, str):
        user_id = str(user_id)
    
    # Basic validation - should not be empty
    if not user_id.strip():
        raise ValueError("User ID cannot be empty")
    
    return user_id.strip()

# -----------------------------
# Enhanced Canonicalization (Critical Fix #3)
# -----------------------------
def enhanced_canonicalize_payment_method(payment_method: str) -> str:
    """
    Enhanced payment method canonicalization with fuzzy matching
    """
    if not payment_method:
        return None
    
    payment_method = payment_method.strip().lower()
    
    # Direct mappings
    direct_mappings = {
        "cash": "Cash",
        "credit card": "Credit Card",
        "debit card": "Debit Card",
        "bank transfer": "Bank Transfer",
        "paypal": "PayPal",
        "venmo": "Venmo",
        "zelle": "Zelle",
        "apple pay": "Apple Pay",
        "google pay": "Google Pay",
        "check": "Check",
        "cheque": "Check"
    }
    
    if payment_method in direct_mappings:
        return direct_mappings[payment_method]
    
    # Common variations
    variations = {
        "cc": "Credit Card",
        "dc": "Debit Card",
        "bt": "Bank Transfer",
        "pp": "PayPal",
        "ap": "Apple Pay",
        "gp": "Google Pay"
    }
    
    if payment_method in variations:
        return variations[payment_method]
    
    # Fuzzy matching for partial matches
    for key, value in direct_mappings.items():
        if key in payment_method or payment_method in key:
            return value
    
    # If no match found, return original (capitalized)
    return payment_method.title()

# -----------------------------
# LLM Provider / Model
# -----------------------------
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
model = GoogleModel("gemini-1.5-flash", provider=provider)

# -----------------------------
# Enhanced System Prompt
# -----------------------------
SYSTEM_PROMPT = """
You are a Query Parser Agent. Convert user natural language into JSON matching the QueryRequest schema.

Your database table `Expense` has these columns:
- id: String
- user_id: String (ALWAYS use the exact user_id provided)
- amount: Decimal (numeric, can aggregate)
- category: String
- subcategory: String? (optional)
- date: DateTime
- paymentMethod: String? (optional)
- description: String? (optional)
- createdAt: DateTime
- companions: String[] (array of strings)

Rules:
1. ALWAYS include "user_id" exactly as provided
2. Only use these filters: category, subcategory, companions, paymentMethod, min_amount, max_amount, date_range.start, date_range.end
3. Aggregate only numeric fields: amount
4. group_by is allowed only on scalar fields (cannot group_by companions)
5. Output strictly JSON matching QueryRequest schema
6. Provide defaults where necessary: limit=100, offset=0, aggregate_field='amount', sort_order='desc'

IMPORTANT: You will receive deterministic extractions in the input. Use them as guidance but make your own decisions.

Examples:

User: "How much did I spend last month?" (user_id=22f8e821-16ea-4f98-a945-30f0e20181f5)
Output:
{
  "user_id": "22f8e821-16ea-4f98-a945-30f0e20181f5",
  "filters": {
    "date_range": {"start": "2025-08-01", "end": "2025-08-31"}
  },
  "aggregate": "sum",
  "aggregate_field": "amount",
  "group_by": null,
  "limit": 100,
  "offset": 0,
  "sort_by": "date",
  "sort_order": "desc"
}

User: "Show all my food expenses with Alice" (user_id=22f8e821-16ea-4f98-a945-30f0e20181f5)
Output:
{
  "user_id": "22f8e821-16ea-4f98-a945-30f0e20181f5",
  "filters": {
    "category": "Food",
    "companions": ["Alice"]
  },
  "aggregate": null,
  "aggregate_field": "amount",
  "group_by": null,
  "limit": 100,
  "offset": 0,
  "sort_by": "date",
  "sort_order": "desc"
}
"""

# -----------------------------
# Query Parser Agent
# -----------------------------
query_parser_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=QueryRequest,
)

# -----------------------------
# FIXED Pydantic Safety Function (Critical Fix #4)
# -----------------------------
def _pydantic_safe(qdict: Dict[str, Any], user_id: str) -> QueryRequest:
    """
    Convert to QueryRequest safely with enhanced error handling
    FIXED: Properly handles None filters and missing extras
    """
    try:
        # Validate user_id first
        user_id = validate_user_id(user_id)
        qdict["user_id"] = user_id
        
        # Ensure filters exists and is properly structured
        if "filters" not in qdict or qdict["filters"] is None:
            qdict["filters"] = {}
        
        # Ensure extras exists within filters
        if "extras" not in qdict["filters"] or qdict["filters"]["extras"] is None:
            qdict["filters"]["extras"] = {}
        
        # Create QueryRequest
        qr = QueryRequest(**qdict)
        
        # Apply enhanced canonicalization
        canonical = {}
        if qr.filters and qr.filters.category:
            canonical["category"] = canonicalize_category(qr.filters.category)
        else:
            canonical["category"] = None
            
        # Enhanced payment method canonicalization
        if qr.filters and qr.filters.paymentMethod:
            canonical["paymentMethod"] = enhanced_canonicalize_payment_method(qr.filters.paymentMethod)
        else:
            canonical["paymentMethod"] = None
        
        # Safely set canonical data
        if qr.filters and qr.filters.extras is not None:
            qr.filters.extras["canonical"] = canonical
        else:
            # If extras is still None, create it
            qr.filters.extras = {"canonical": canonical}
            
        return qr
        
    except Exception as e:
        logger.exception(f"Failed to create QueryRequest: {e}")
        # Return minimal safe QueryRequest
        return QueryRequest(
            user_id=user_id,
            filters=QueryFilters(extras={"error": str(e), "canonical": {"category": None, "paymentMethod": None}}),
            limit=100,
            offset=0,
            sort_by="date",
            sort_order="desc"
        )

# -----------------------------
# Enhanced Reconciliation Logic
# -----------------------------
def _reconcile_with_preparse(parsed: QueryRequest, pre: Dict[str, Any], user_id: str) -> QueryRequest:
    """
    Enhanced reconciliation that prioritizes deterministic extractions
    and uses LLM to choose from candidates rather than invent new ones.
    """
    p = parsed.model_dump()
    sources = {}
    confidence = {}
    extras = {}

    # Amount handling: deterministic takes priority
    if pre.get("min_amount") is not None:
        p["filters"]["min_amount"] = pre["min_amount"]
        sources["min_amount"] = "deterministic"
        confidence["min_amount"] = 1.0
    else:
        sources["min_amount"] = "llm" if p["filters"].get("min_amount") is not None else None
        confidence["min_amount"] = 0.9 if p["filters"].get("min_amount") else None

    if pre.get("max_amount") is not None:
        p["filters"]["max_amount"] = pre["max_amount"]
        sources["max_amount"] = "deterministic"
        confidence["max_amount"] = 1.0
    else:
        sources["max_amount"] = "llm" if p["filters"].get("max_amount") is not None else None
        confidence["max_amount"] = 0.9 if p["filters"].get("max_amount") else None

    # Date handling: deterministic takes priority
    if pre.get("date_range") is not None:
        p["filters"]["date_range"] = pre["date_range"]
        sources["date_range"] = "deterministic"
        confidence["date_range"] = 1.0
    else:
        sources["date_range"] = "llm" if p["filters"].get("date_range") else None
        confidence["date_range"] = 0.9 if p["filters"].get("date_range") else None

    # Companions: merge deterministic and LLM, prioritize deterministic
    if pre.get("companions"):
        llm_comp = p["filters"].get("companions") or []
        det_comp = pre.get("companions") or []
        merged = list(dict.fromkeys((det_comp + llm_comp)))  # preserve order, unique
        p["filters"]["companions"] = merged or None
        sources["companions"] = "both" if llm_comp else "deterministic"
        confidence["companions"] = 1.0 if det_comp else 0.7
    else:
        sources["companions"] = "llm" if p["filters"].get("companions") else None
        confidence["companions"] = 0.7 if p["filters"].get("companions") else None

    # Payment method: deterministic takes priority
    if pre.get("payment_methods"):
        p["filters"]["paymentMethod"] = pre["payment_methods"][0]
        sources["paymentMethod"] = "deterministic"
        confidence["paymentMethod"] = 1.0
    else:
        sources["paymentMethod"] = "llm" if p["filters"].get("paymentMethod") else None
        confidence["paymentMethod"] = 0.7 if p["filters"].get("paymentMethod") else None

    # ENHANCED CATEGORY LOGIC: Inverted - LLM chooses from deterministic candidates
    if pre.get("candidate_categories"):
        # If we have deterministic candidates, use the LLM's choice from them
        # But if LLM provided a category not in candidates, validate it
        llm_category = p["filters"].get("category")
        if llm_category and llm_category.lower() in [cat.lower() for cat in pre["candidate_categories"]]:
            # LLM chose from our candidates - good!
            sources["category"] = "llm_from_candidates"
            confidence["category"] = 0.9
        elif llm_category:
            # LLM provided a category not in our candidates - be suspicious
            # Keep the LLM choice but mark it as potentially unreliable
            sources["category"] = "llm_override"
            confidence["category"] = 0.5
            extras.setdefault("warnings", []).append(f"LLM chose '{llm_category}' not in deterministic candidates {pre['candidate_categories']}")
        else:
            # LLM didn't provide category, use first deterministic candidate
            p["filters"]["category"] = pre["candidate_categories"][0]
            sources["category"] = "deterministic"
            confidence["category"] = 0.85
    else:
        # No deterministic candidates, trust LLM
        sources["category"] = "llm" if p["filters"].get("category") else None
        confidence["category"] = 0.7 if p["filters"].get("category") else None

    # Store metadata
    extras["pre_parse"] = pre
    extras["sources"] = sources
    extras["confidence"] = confidence

    # Enhanced validation
    try:
        if p["filters"].get("min_amount") and p["filters"].get("max_amount"):
            if p["filters"]["min_amount"] > p["filters"]["max_amount"]:
                p["filters"]["min_amount"], p["filters"]["max_amount"] = p["filters"]["max_amount"], p["filters"]["min_amount"]
                extras.setdefault("repairs", []).append("swapped_min_max")
    except Exception:
        pass

    # Enhanced ambiguity detection
    has_date = bool(p["filters"].get("date_range"))
    has_amount = bool(p["filters"].get("min_amount") or p["filters"].get("max_amount"))
    has_category = bool(p["filters"].get("category"))
    has_companions = bool(p["filters"].get("companions"))
    has_payment = bool(p["filters"].get("paymentMethod"))
    
    # Consider query ambiguous if it has fewer than 2 specific filters
    specific_filters = sum([has_date, has_amount, has_category, has_companions, has_payment])
    
    if specific_filters < 2:
        extras["needs_confirmation"] = True
        extras["clarify"] = extras.get("clarify") or [
            "Which time period do you want to query?",
            "Do you want to filter by category or show all expenses?"
        ]

    return _pydantic_safe(p, user_id)

# -----------------------------
# Enhanced Fallback Query Creation
# -----------------------------
def _create_fallback_query(pre: Dict[str, Any], user_input: str, user_id: str) -> QueryRequest:
    """
    Create a fallback query using only deterministic parsing when LLM fails
    """
    # Create a proper QueryFilters object
    filters = QueryFilters()
    
    # Use deterministic date range if available
    if pre.get("date_range"):
        filters.date_range = pre["date_range"]
    
    # Use deterministic payment methods if available
    if pre.get("payment_methods"):
        # Take the first payment method as primary
        filters.paymentMethod = pre["payment_methods"][0]
    
    # Use deterministic companions if available
    if pre.get("companions"):
        filters.companions = pre["companions"]
    
    # Use deterministic categories if available
    if pre.get("candidate_categories"):
        filters.category = pre["candidate_categories"][0]
    
    # Determine aggregate based on query intent
    aggregate = "sum"
    if any(word in user_input.lower() for word in ["average", "avg", "mean"]):
        aggregate = "avg"
    elif any(word in user_input.lower() for word in ["count", "how many", "number"]):
        aggregate = "count"
    
    return QueryRequest(
        user_id=user_id,
        filters=filters,
        aggregate=aggregate,
        aggregate_field="amount",
        limit=100,
        offset=0,
        sort_by="date",
        sort_order="desc"
    )

# -----------------------------
# Main parsing function with rate limiting
# -----------------------------
@with_rate_limiting
async def parse_query_with_fallback(user_input: str, user_id: str, context: Optional[Dict[str, Any]] = None) -> QueryRequest:
    """
    Enhanced query parsing with rate limiting and comprehensive fallbacks
    """
    try:
        # Validate user_id first
        user_id = validate_user_id(user_id)
        
        # Step 1: Deterministic pre-parsing
        pre = pre_parse(user_input)
        logger.info(f"Pre-parse result: {pre}")
        
        # Step 2: Create enhanced input for LLM with deterministic context
        enhanced_input = f"User query: {user_input}\n"
        if pre.get("candidate_categories"):
            enhanced_input += f"Detected categories: {', '.join(pre['candidate_categories'])}\n"
        if pre.get("companions"):
            enhanced_input += f"Detected companions: {', '.join(pre['companions'])}\n"
        if pre.get("date_range"):
            enhanced_input += f"Detected date range: {pre['date_range']}\n"
        if pre.get("payment_methods"):
            enhanced_input += f"Detected payment methods: {', '.join(pre['payment_methods'])}\n"
        
        enhanced_input += f"User ID: {user_id}"
        
        # Step 3: LLM parsing with error handling
        try:
            parsed = await query_parser_agent.run(enhanced_input)
            logger.info(f"LLM parse result: {parsed}")
            
            # Step 4: Enhanced reconciliation
            final_result = _reconcile_with_preparse(parsed.output, pre, user_id)
            logger.info(f"Final reconciled result: {final_result}")
            
            return final_result
            
        except Exception as llm_error:
            logger.warning(f"LLM parsing failed: {llm_error}")
            
            # Fallback: Use deterministic parsing only
            logger.info("Falling back to deterministic parsing only")
            return _create_fallback_query(pre, user_input, user_id)
        
    except Exception as e:
        logger.error(f"Query parsing failed completely: {e}")
        # Ultimate fallback: basic query with just user_id
        return QueryRequest(
            user_id=user_id,
            filters=QueryFilters(),
            aggregate="sum",
            aggregate_field="amount",
            limit=100,
            offset=0,
            sort_by="date",
            sort_order="desc"
        )

# -----------------------------
# Backward compatibility wrapper
# -----------------------------
async def parse_query(user_input: str, user_id: str, context: Optional[Dict[str, Any]] = None) -> QueryRequest:
    """
    Backward compatibility wrapper for the enhanced parsing function
    """
    return await parse_query_with_fallback(user_input, user_id, context)