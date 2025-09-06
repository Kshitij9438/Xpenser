# FILE: test_phase1_fixes.py
"""
Test suite for Phase 1 critical fixes
"""

import asyncio
import pytest
from agents.query_parser_improved import (
    parse_query_with_fallback,
    validate_user_id,
    enhanced_canonicalize_payment_method,
    enhanced_canonicalize_category,
    APIRateLimiter
)
from services.canonicalizer_improved import (
    enhanced_canonicalize_payment_method as service_canonicalize_payment,
    enhanced_canonicalize_category as service_canonicalize_category
)

# -----------------------------
# Test User ID Validation
# -----------------------------
def test_user_id_validation():
    """Test user ID validation and normalization"""
    
    # Valid cases
    assert validate_user_id("22f8e821-16ea-4f98-a945-30f0e20181f5") == "22f8e821-16ea-4f98-a945-30f0e20181f5"
    assert validate_user_id(123) == "123"
    assert validate_user_id(123.0) == "123"
    assert validate_user_id("  alice  ") == "alice"
    
    # Invalid cases
    with pytest.raises(ValueError):
        validate_user_id(None)
    
    with pytest.raises(ValueError):
        validate_user_id("")
    
    with pytest.raises(ValueError):
        validate_user_id("   ")

# -----------------------------
# Test Payment Method Canonicalization
# -----------------------------
def test_payment_method_canonicalization():
    """Test enhanced payment method canonicalization"""
    
    # Direct mappings
    assert enhanced_canonicalize_payment_method("cash") == "Cash"
    assert enhanced_canonicalize_payment_method("credit card") == "Credit Card"
    assert enhanced_canonicalize_payment_method("paypal") == "PayPal"
    
    # Variations
    assert enhanced_canonicalize_payment_method("cc") == "Credit Card"
    assert enhanced_canonicalize_payment_method("pp") == "PayPal"
    assert enhanced_canonicalize_payment_method("ap") == "Apple Pay"
    
    # Fuzzy matching
    assert enhanced_canonicalize_payment_method("credit") == "Credit Card"
    assert enhanced_canonicalize_payment_method("debit") == "Debit Card"
    
    # Edge cases
    assert enhanced_canonicalize_payment_method("") is None
    assert enhanced_canonicalize_payment_method(None) is None
    assert enhanced_canonicalize_payment_method("unknown method") == "Unknown Method"

# -----------------------------
# Test Category Canonicalization
# -----------------------------
def test_category_canonicalization():
    """Test enhanced category canonicalization"""
    
    # Direct mappings
    assert enhanced_canonicalize_category("food") == "Food"
    assert enhanced_canonicalize_category("transportation") == "Transportation"
    assert enhanced_canonicalize_category("entertainment") == "Entertainment"
    
    # Variations
    assert enhanced_canonicalize_category("restaurant") == "Food"
    assert enhanced_canonicalize_category("dining") == "Food"
    assert enhanced_canonicalize_category("groceries") == "Food"
    
    # Fuzzy matching
    assert enhanced_canonicalize_category("food & dining") == "Food"
    assert enhanced_canonicalize_category("fast food") == "Food"
    
    # Edge cases
    assert enhanced_canonicalize_category("") is None
    assert enhanced_canonicalize_category(None) is None
    assert enhanced_canonicalize_category("unknown category") == "Unknown Category"

# -----------------------------
# Test API Rate Limiting
# -----------------------------
async def test_api_rate_limiting():
    """Test API rate limiting functionality"""
    
    rate_limiter = APIRateLimiter(max_requests_per_minute=2)
    
    # First two requests should go through immediately
    start_time = asyncio.get_event_loop().time()
    await rate_limiter.acquire()
    await rate_limiter.acquire()
    
    # Third request should be rate limited
    await rate_limiter.acquire()
    end_time = asyncio.get_event_loop().time()
    
    # Should have waited at least 60 seconds
    assert end_time - start_time >= 60

# -----------------------------
# Test Query Parsing with Fallbacks
# -----------------------------
async def test_query_parsing_fallbacks():
    """Test query parsing with various fallback scenarios"""
    
    # Test with valid input
    result = await parse_query_with_fallback(
        "How much did I spend on food last month?",
        "22f8e821-16ea-4f98-a945-30f0e20181f5"
    )
    
    assert result.user_id == "22f8e821-16ea-4f98-a945-30f0e20181f5"
    assert result.filters is not None
    assert result.aggregate == "sum"
    assert result.aggregate_field == "amount"
    
    # Test with numeric user ID
    result = await parse_query_with_fallback(
        "Show my expenses",
        123
    )
    
    assert result.user_id == "123"
    
    # Test with invalid user ID (should raise error)
    with pytest.raises(ValueError):
        await parse_query_with_fallback(
            "Show my expenses",
            None
        )

# -----------------------------
# Test Pydantic Safety
# -----------------------------
def test_pydantic_safety():
    """Test the fixed Pydantic safety function"""
    
    from agents.query_parser_improved import _pydantic_safe
    
    # Test with proper data
    qdict = {
        "filters": {
            "category": "Food",
            "extras": {}
        },
        "aggregate": "sum",
        "limit": 100
    }
    
    result = _pydantic_safe(qdict, "test-user")
    assert result.user_id == "test-user"
    assert result.filters.category == "Food"
    assert result.filters.extras is not None
    
    # Test with None filters
    qdict = {
        "filters": None,
        "aggregate": "sum",
        "limit": 100
    }
    
    result = _pydantic_safe(qdict, "test-user")
    assert result.user_id == "test-user"
    assert result.filters is not None
    assert result.filters.extras is not None
    
    # Test with missing filters
    qdict = {
        "aggregate": "sum",
        "limit": 100
    }
    
    result = _pydantic_safe(qdict, "test-user")
    assert result.user_id == "test-user"
    assert result.filters is not None
    assert result.filters.extras is not None

# -----------------------------
# Run all tests
# -----------------------------
if __name__ == "__main__":
    # Run synchronous tests
    test_user_id_validation()
    test_payment_method_canonicalization()
    test_category_canonicalization()
    test_pydantic_safety()
    
    # Run asynchronous tests
    asyncio.run(test_api_rate_limiting())
    asyncio.run(test_query_parsing_fallbacks())
    
    print("✅ All Phase 1 critical fixes tests passed!")
