# FILE: services/canonicalizer.py
"""
PHASE 1 CRITICAL FIXES - Enhanced Canonicalization
- Improved payment method canonicalization
- Better fuzzy matching
- Enhanced category canonicalization
"""

import re
from typing import Optional, Dict, List
from difflib import get_close_matches

# -----------------------------
# Enhanced Payment Method Canonicalization
# -----------------------------
def enhanced_canonicalize_payment_method(payment_method: str) -> Optional[str]:
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
        "cheque": "Check",
        "wire transfer": "Wire Transfer",
        "ach": "ACH Transfer",
        "crypto": "Cryptocurrency",
        "bitcoin": "Bitcoin",
        "ethereum": "Ethereum"
    }
    
    if payment_method in direct_mappings:
        return direct_mappings[payment_method]
    
    # Common variations and abbreviations
    variations = {
        "cc": "Credit Card",
        "dc": "Debit Card",
        "bt": "Bank Transfer",
        "pp": "PayPal",
        "ap": "Apple Pay",
        "gp": "Google Pay",
        "wt": "Wire Transfer",
        "ach": "ACH Transfer",
        "btc": "Bitcoin",
        "eth": "Ethereum"
    }
    
    if payment_method in variations:
        return variations[payment_method]
    
    # Fuzzy matching for partial matches
    for key, value in direct_mappings.items():
        if key in payment_method or payment_method in key:
            return value
    
    # Advanced fuzzy matching using difflib
    close_matches = get_close_matches(payment_method, direct_mappings.keys(), n=1, cutoff=0.6)
    if close_matches:
        return direct_mappings[close_matches[0]]
    
    # If no match found, return original (capitalized)
    return payment_method.title()

# -----------------------------
# Enhanced Category Canonicalization
# -----------------------------
def enhanced_canonicalize_category(category: str) -> Optional[str]:
    """
    Enhanced category canonicalization with better fuzzy matching
    """
    if not category:
        return None
    
    category = category.strip().lower()
    
    # Direct mappings
    direct_mappings = {
        "food": "Food",
        "restaurant": "Food",
        "dining": "Food",
        "groceries": "Food",
        "transportation": "Transportation",
        "transport": "Transportation",
        "travel": "Transportation",
        "entertainment": "Entertainment",
        "shopping": "Shopping",
        "utilities": "Utilities",
        "healthcare": "Healthcare",
        "medical": "Healthcare",
        "education": "Education",
        "housing": "Housing",
        "rent": "Housing",
        "insurance": "Insurance",
        "personal care": "Personal Care",
        "beauty": "Personal Care",
        "gifts": "Gifts",
        "donations": "Donations",
        "charity": "Donations",
        "business": "Business",
        "work": "Business",
        "office": "Business",
        "subscriptions": "Subscriptions",
        "software": "Subscriptions",
        "memberships": "Subscriptions"
    }
    
    if category in direct_mappings:
        return direct_mappings[category]
    
    # Common variations
    variations = {
        "food & dining": "Food",
        "food and dining": "Food",
        "restaurants": "Food",
        "fast food": "Food",
        "coffee": "Food",
        "cafe": "Food",
        "gas": "Transportation",
        "fuel": "Transportation",
        "uber": "Transportation",
        "lyft": "Transportation",
        "taxi": "Transportation",
        "public transport": "Transportation",
        "movies": "Entertainment",
        "cinema": "Entertainment",
        "theater": "Entertainment",
        "games": "Entertainment",
        "gaming": "Entertainment",
        "clothes": "Shopping",
        "clothing": "Shopping",
        "electronics": "Shopping",
        "books": "Shopping",
        "electricity": "Utilities",
        "water": "Utilities",
        "internet": "Utilities",
        "phone": "Utilities",
        "doctor": "Healthcare",
        "pharmacy": "Healthcare",
        "medicine": "Healthcare",
        "school": "Education",
        "university": "Education",
        "course": "Education",
        "mortgage": "Housing",
        "maintenance": "Housing",
        "repairs": "Housing",
        "car insurance": "Insurance",
        "health insurance": "Insurance",
        "life insurance": "Insurance",
        "haircut": "Personal Care",
        "spa": "Personal Care",
        "gym": "Personal Care",
        "fitness": "Personal Care",
        "present": "Gifts",
        "birthday": "Gifts",
        "wedding": "Gifts",
        "nonprofit": "Donations",
        "ngo": "Donations",
        "meeting": "Business",
        "conference": "Business",
        "netflix": "Subscriptions",
        "spotify": "Subscriptions",
        "amazon prime": "Subscriptions",
        "youtube": "Subscriptions"
    }
    
    if category in variations:
        return variations[category]
    
    # Fuzzy matching for partial matches
    for key, value in direct_mappings.items():
        if key in category or category in key:
            return value
    
    # Advanced fuzzy matching using difflib
    close_matches = get_close_matches(category, direct_mappings.keys(), n=1, cutoff=0.6)
    if close_matches:
        return direct_mappings[close_matches[0]]
    
    # If no match found, return original (capitalized)
    return category.title()

# -----------------------------
# Enhanced Companion Canonicalization
# -----------------------------
def enhanced_canonicalize_companion(companion: str) -> Optional[str]:
    """
    Enhanced companion canonicalization with name normalization
    """
    if not companion:
        return None
    
    companion = companion.strip()
    
    # Common name variations
    name_variations = {
        "alice": "Alice",
        "bob": "Bob",
        "charlie": "Charlie",
        "david": "David",
        "eve": "Eve",
        "frank": "Frank",
        "grace": "Grace",
        "henry": "Henry",
        "ivy": "Ivy",
        "jack": "Jack",
        "kate": "Kate",
        "liam": "Liam",
        "mia": "Mia",
        "noah": "Noah",
        "olivia": "Olivia",
        "paul": "Paul",
        "quinn": "Quinn",
        "rachel": "Rachel",
        "sam": "Sam",
        "taylor": "Taylor",
        "una": "Una",
        "victor": "Victor",
        "willa": "Willa",
        "xavier": "Xavier",
        "yara": "Yara",
        "zoe": "Zoe"
    }
    
    companion_lower = companion.lower()
    if companion_lower in name_variations:
        return name_variations[companion_lower]
    
    # If no match found, return original (properly capitalized)
    return companion.title()

# -----------------------------
# Backward compatibility
# -----------------------------
def canonicalize_category(category: str) -> Optional[str]:
    """Backward compatibility wrapper"""
    return enhanced_canonicalize_category(category)

def canonicalize_payment_method(payment_method: str) -> Optional[str]:
    """Backward compatibility wrapper"""
    return enhanced_canonicalize_payment_method(payment_method)

def canonicalize_companion(companion: str) -> Optional[str]:
    """Backward compatibility wrapper"""
    return enhanced_canonicalize_companion(companion)