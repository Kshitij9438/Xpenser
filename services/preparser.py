# FILE: services/preparser.py
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# Optional: if you have dateparser installed, it's better.
try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False
    print("Warning: dateparser not installed. Install with: pip install dateparser")

# Current timezone-aware "now"
NOW = datetime.now()

# -----------------------------
# Cardinality detection (CRITICAL FIX)
# -----------------------------
CARDINALITY_KEYWORDS = {
    "transaction", "transactions",
    "record", "records",
    "entry", "entries",
    "expense", "expenses",
    "top", "highest", "largest", "heaviest"
}

def extract_cardinality(text: str) -> Optional[int]:
    """
    Detect numbers that refer to result count
    e.g. '3 transactions', 'top 5 expenses'
    """
    text_lower = text.lower()
    tokens = re.findall(r'\b\d+\b|\b[a-zA-Z]+\b', text_lower)

    for i, tok in enumerate(tokens):
        if tok.isdigit():
            window = tokens[max(0, i - 2): i + 3]
            if any(w in CARDINALITY_KEYWORDS for w in window):
                return int(tok)
    return None

# -----------------------------
# Payment methods
# -----------------------------
PAYMENT_TOKENS = [
    "netbanking", "upi", "gpay", "google pay", "phonepe", "paytm",
    "credit card", "debit card", "card", "cash", "bank transfer", "salary account"
]

# -----------------------------
# Category keywords
# -----------------------------
CATEGORY_KEYWORDS = {
    "food": ["food", "dinner", "lunch", "breakfast", "restaurant", "cafe", "dining", "meal", "eat", "ate"],
    "groceries": ["grocery", "groceries", "supermarket", "bigbasket", "vegetables", "fruits"],
    "travel": ["uber", "ola", "taxi", "flight", "train", "bus", "travel", "cab", "metro", "auto"],
    "shopping": ["mall", "shopping", "amazon", "clothes", "shirts", "buy", "bought", "purchase", "items"],
    "entertainment": ["movie", "cinema", "netflix", "prime", "spotify", "game", "gaming", "concert"],
    "health": ["hospital", "doctor", "medicine", "pharmacy", "medical", "health"],
    "bills": ["electricity", "water", "internet", "phone", "rent", "bill", "bills"],
    "education": ["school", "college", "course", "book", "books", "education", "tuition"]
}

CATEGORY_PRIORITY = {
    "food": 1, "groceries": 2, "travel": 3, "shopping": 4,
    "entertainment": 5, "health": 6, "bills": 7, "education": 8
}

MONTH_NAMES = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12
}

# -----------------------------
# Amount parsing
# -----------------------------
def _clean_num(tok: str) -> Optional[float]:
    tok = tok.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("INR", "")
    tok = tok.replace(",", "").strip()
    try:
        return float(tok)
    except Exception:
        return None

_amount_re = re.compile(
    r'(?:₹\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:rupee|rs|₹|INR)?',
    re.IGNORECASE
)

def extract_amounts(text: str) -> List[float]:
    amounts = []
    for m in _amount_re.finditer(text):
        val = _clean_num(m.group(1))
        if val is not None:
            amounts.append(val)
    return amounts

# -----------------------------
# Date parsing
# -----------------------------
def _parse_date_fallback(day: int, month_name: str, year: int) -> Optional[Dict[str, str]]:
    try:
        month_num = int(month_name) if month_name.isdigit() else MONTH_NAMES.get(month_name.lower())
        if not month_num:
            return None
        d = datetime(year, month_num, day)
        s = d.strftime("%Y-%m-%d")
        return {"start": s, "end": s}
    except Exception:
        return None

def extract_date_range(text: str) -> Optional[Dict[str, str]]:
    text_lower = text.lower()
    today = NOW

    if "last month" in text_lower:
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}

    if "this month" in text_lower:
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
        return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}

    if "today" in text_lower:
        d = today.strftime("%Y-%m-%d")
        return {"start": d, "end": d}

    if "yesterday" in text_lower:
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return {"start": d, "end": d}

    return None

# -----------------------------
# Companion extraction
# -----------------------------
def extract_companions(text: str) -> Optional[List[str]]:
    companions = []
    match = re.search(r'\bwith\s+([A-Za-z][A-Za-z\'\.\s,&-]+)', text, re.IGNORECASE)
    if match:
        parts = re.split(r',| and | & ', match.group(1))
        companions.extend(p.strip() for p in parts if p.strip())
    return companions or None

# -----------------------------
# Payment & category extraction
# -----------------------------
def extract_payment_methods(text: str) -> Optional[List[str]]:
    text_lower = text.lower()
    return [p for p in PAYMENT_TOKENS if p in text_lower] or None

def extract_candidate_categories(text: str) -> Optional[List[str]]:
    text_lower = text.lower()
    found = []
    for cat, keys in CATEGORY_KEYWORDS.items():
        if any(k in text_lower for k in keys):
            found.append(cat)
    if not found:
        return None
    found.sort(key=lambda x: CATEGORY_PRIORITY.get(x, 999))
    return found

# -----------------------------
# MAIN PRE-PARSE
# -----------------------------
def pre_parse(text: str) -> Dict[str, Any]:
    """
    Deterministic pre-parser with cardinality awareness
    """
    cardinality = extract_cardinality(text)
    amounts = extract_amounts(text)
    date_range = extract_date_range(text)
    companions = extract_companions(text)
    payment_methods = extract_payment_methods(text)
    candidate_categories = extract_candidate_categories(text)

    min_amount = None
    max_amount = None

    # Only treat numbers as money if NOT cardinality
    if amounts and cardinality is None:
        if re.search(r'\bbetween\b', text.lower()) or re.search(r'\bto\b', text.lower()):
            min_amount = min(amounts)
            max_amount = max(amounts)
        else:
            min_amount = amounts[0]
            max_amount = amounts[0]

    return {
        "amounts": amounts,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "limit": cardinality,
        "date_range": date_range,
        "companions": companions,
        "payment_methods": payment_methods,
        "candidate_categories": candidate_categories,
        "raw_text": text
    }
