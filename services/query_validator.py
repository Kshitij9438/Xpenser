# FILE: services/query_validator.py
"""
Enhanced validation layer to catch hallucinations and inconsistencies
"""

import logging
import re
from typing import Dict, Any, Optional, List
from models.query import QueryResult, NLPResponse

logger = logging.getLogger("query_validator")

def validate_query_response(db_result: QueryResult, nlp_response: NLPResponse, original_query: str = "") -> Optional[str]:
    """
    Enhanced validation that checks for hallucinations and inconsistencies.
    Returns a warning message if inconsistencies are found, None if valid.
    """
    try:
        print(f"[VALIDATION] Validating response for query: {original_query}")
        print(f"[VALIDATION] DB result: {db_result}")
        print(f"[VALIDATION] NLP response: {nlp_response.answer}")
        
        # Extract key numerical data from database result
        db_amount = None
        db_count = None
        if hasattr(db_result, 'aggregate_result') and db_result.aggregate_result:
            if hasattr(db_result.aggregate_result, 'sum'):
                db_amount = db_result.aggregate_result.sum
            if hasattr(db_result.aggregate_result, 'count'):
                db_count = db_result.aggregate_result.count
        
        # Extract key data from NLP response
        answer = nlp_response.answer.lower()
        
        # Check for amount inconsistencies
        if db_amount is not None:
            # Look for amount mentions in the answer
            amount_matches = re.findall(r'[₹$]?(\d+(?:,\d{3})*(?:\.\d+)?)', answer)
            if amount_matches:
                mentioned_amounts = [float(amt.replace(',', '')) for amt in amount_matches]
                # Check if any mentioned amount is significantly different from DB result
                for mentioned_amt in mentioned_amounts:
                    if abs(mentioned_amt - db_amount) > 0.01:  # Allow small floating point differences
                        warning = f"Amount mismatch: DB has {db_amount}, answer mentions {mentioned_amt}"
                        print(f"[VALIDATION] {warning}")
                        return warning
        
        # Check for date inconsistencies - ENHANCED
        if "between" in answer or "from" in answer:
            # Check if the original query was asking for a specific date, not a range
            if re.search(r'\d{1,2}[st|nd|rd|th]?\s+(?:of\s+)?\w+\s+\d{4}', original_query, re.IGNORECASE):
                # Original query was for a specific date, but answer mentions a range
                warning = "Date range mentioned in answer but query was for specific date"
                print(f"[VALIDATION] {warning}")
                return warning
        
        # Check for multiple dates when only one was requested - ENHANCED
        if re.search(r'\d{1,2}[st|nd|rd|th]?\s+(?:of\s+)?\w+\s+\d{4}', original_query, re.IGNORECASE):
            # Original query was for a specific date
            original_date_match = re.search(r'(\d{1,2})[st|nd|rd|th]?\s+(?:of\s+)?(\w+)\s+(\d{4})', original_query, re.IGNORECASE)
            if original_date_match:
                original_day = original_date_match.group(1)
                original_month = original_date_match.group(2)
                original_year = original_date_match.group(3)
                
                print(f"[VALIDATION] Looking for date: {original_month} {original_day}, {original_year}")
                
                # Count how many different dates are mentioned in the answer
                date_matches = re.findall(r'(\w+)\s+(\d{1,2})[st|nd|rd|th]?[,\s]*(\d{4})', nlp_response.answer, re.IGNORECASE)
                print(f"[VALIDATION] Found {len(date_matches)} dates in answer: {date_matches}")
                
                if len(date_matches) > 1:
                    warning = f"Query was for {original_month} {original_day}, {original_year} but answer shows {len(date_matches)} different dates"
                    print(f"[VALIDATION] {warning}")
                    return warning
                
                # Check if the specific requested date is mentioned
                requested_date_mentioned = False
                for month, day, year in date_matches:
                    if (day == original_day and 
                        month.lower() == original_month.lower() and 
                        year == original_year):
                        requested_date_mentioned = True
                        print(f"[VALIDATION] Found requested date in answer")
                        break
                
                if not requested_date_mentioned and date_matches:
                    warning = f"Requested date {original_month} {original_day}, {original_year} not found in answer"
                    print(f"[VALIDATION] {warning}")
                    return warning
        
        # Check for companion inconsistencies
        if hasattr(db_result, 'filters') and db_result.filters and db_result.filters.companions:
            db_companions = [c.lower() for c in db_result.filters.companions]
            for companion in db_companions:
                if companion not in answer:
                    print(f"[VALIDATION] Warning: Companion '{companion}' not mentioned in answer")
        
        # Check for payment method inconsistencies
        if hasattr(db_result, 'filters') and db_result.filters and db_result.filters.paymentMethod:
            db_payment = db_result.filters.paymentMethod.lower()
            if db_payment not in answer:
                print(f"[VALIDATION] Warning: Payment method '{db_payment}' not mentioned in answer")
        
        # Check for category inconsistencies
        if hasattr(db_result, 'filters') and db_result.filters and db_result.filters.category:
            db_category = db_result.filters.category.lower()
            if db_category not in answer:
                print(f"[VALIDATION] Warning: Category '{db_category}' not mentioned in answer")
        
        # Check for overly specific details that might be hallucinated
        # If the answer mentions specific details not in the query, flag it
        answer_words = set(answer.split())
        query_words = set(original_query.lower().split())
        
        # Look for potentially hallucinated details
        suspicious_words = ['taxi', 'ride', 'restaurant', 'meal', 'shopping', 'mall', 'movie', 'cinema']
        for word in suspicious_words:
            if word in answer_words and word not in query_words:
                # This detail wasn't in the original query, might be hallucinated
                print(f"[VALIDATION] Warning: Potentially hallucinated detail '{word}' not in original query")
        
        print(f"[VALIDATION] Validation passed")
        return None  # No inconsistencies found
        
    except Exception as e:
        logger.exception(f"Error in validation: {e}")
        return f"Validation error: {str(e)}"

def create_safe_fallback_response(db_result: QueryResult, user_id: str, original_query: str = "") -> NLPResponse:
    """
    Create a safe, template-based response when validation fails
    """
    try:
        print(f"[FALLBACK] Creating safe response for query: {original_query}")
        
        if hasattr(db_result, 'aggregate_result') and db_result.aggregate_result:
            if hasattr(db_result.aggregate_result, 'sum'):
                amount = db_result.aggregate_result.sum
                return NLPResponse(
                    user_id=user_id,
                    answer=f"Total amount spent: ₹{amount:,.2f}",
                    context={"fallback": True, "source": "template", "original_query": original_query}
                )
            elif hasattr(db_result.aggregate_result, 'count'):
                count = db_result.aggregate_result.count
                return NLPResponse(
                    user_id=user_id,
                    answer=f"Found {count} matching records",
                    context={"fallback": True, "source": "template", "original_query": original_query}
                )
        
        return NLPResponse(
            user_id=user_id,
            answer="Query processed successfully",
            context={"fallback": True, "source": "template", "original_query": original_query}
        )
        
    except Exception as e:
        logger.exception(f"Error creating fallback response: {e}")
        return NLPResponse(
            user_id=user_id,
            answer="There was an issue processing your query",
            context={"fallback": True, "error": str(e), "original_query": original_query}
        )