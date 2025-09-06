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

# Current timezone-aware "now" — adjust if you want to inject user's timezone
NOW = datetime.now()

# Known payment methods (raw tokens we search for)
PAYMENT_TOKENS = [
    "netbanking", "upi", "gpay", "google pay", "phonepe", "paytm",
    "credit card", "debit card", "card", "cash", "bank transfer", "salary account"
]

# Enhanced category keywords with better coverage
CATEGORY_KEYWORDS = {
    "food": ["food", "dinner", "lunch", "breakfast", "restaurant", "cafe", "dining", "meal", "eat", "ate"],
    "groceries": ["grocery", "groceries", "supermarket", "bigbasket", "vegetables", "fruits"],
    "travel": ["uber", "ola", "taxi", "flight", "train", "bus", "travel", "cab", "metro", "auto"],
    "shopping": ["mall", "shopping", "amazon", "clothes", "shirts", "shopping", "buy", "bought", "purchase", "items"],
    "entertainment": ["movie", "cinema", "netflix", "prime", "spotify", "game", "gaming", "concert"],
    "health": ["hospital", "doctor", "medicine", "pharmacy", "medical", "health"],
    "bills": ["electricity", "water", "internet", "phone", "rent", "bill", "bills"],
    "education": ["school", "college", "course", "book", "books", "education", "tuition"]
}

# Category priority mapping for disambiguation
CATEGORY_PRIORITY = {
    "food": 1, "groceries": 2, "travel": 3, "shopping": 4, 
    "entertainment": 5, "health": 6, "bills": 7, "education": 8
}

# Month name mapping
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


def _clean_num(tok: str) -> float:
    tok = tok.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("INR", "")
    tok = tok.replace(",", "").strip()
    try:
        return float(tok)
    except Exception:
        return None


_amount_re = re.compile(r'(?:₹\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:rupee|rs|₹|INR)?', re.IGNORECASE)


def extract_amounts(text: str) -> List[float]:
    amounts = []
    for m in _amount_re.finditer(text):
        raw = m.group(1)
        val = _clean_num(raw)
        if val is not None:
            amounts.append(val)
    return amounts


def _parse_date_fallback(day: int, month_name: str, year: int) -> Optional[Dict[str, str]]:
    """Fallback date parsing without dateparser"""
    try:
        month_num = MONTH_NAMES.get(month_name.lower())
        if not month_num:
            return None
        
        # Create date object
        date_obj = datetime(year, month_num, day)
        date_str = date_obj.strftime("%Y-%m-%d")
        result = {"start": date_str, "end": date_str}
        return result
    except Exception:
        return None


# Enhanced date heuristics with fallback
def extract_date_range(text: str) -> Optional[Dict[str, str]]:
    text_lower = text.lower()

    # common relative phrases
    if "last month" in text_lower:
        today = NOW
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return {"start": last_month_start.strftime("%Y-%m-%d"), "end": last_month_end.strftime("%Y-%m-%d")}

    if "this month" in text_lower:
        today = NOW
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
        return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}

    if "today" in text_lower:
        d = NOW.date().strftime("%Y-%m-%d")
        return {"start": d, "end": d}

    if "yesterday" in text_lower:
        d = (NOW.date() - timedelta(days=1)).strftime("%Y-%m-%d")
        return {"start": d, "end": d}

    # Enhanced patterns for specific dates
    specific_date_patterns = [
        r'(\d{1,2})[st|nd|rd|th]?\s+of\s+(\w+)\s+(\d{4})',  # "8th of April 2025"
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # "8/4/2025" or "8-4-2025"
        r'(\w+)\s+(\d{1,2})[st|nd|rd|th]?[,\s]*(\d{4})',  # "April 8th, 2025"
        r'(\d{1,2})[st|nd|rd|th]?\s+(\w+)\s+(\d{4})',  # "8th April 2025"
    ]
    
    for pattern in specific_date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if HAS_DATEPARSER:
                try:
                    parsed_date = dateparser.parse(match.group(0))
                    if parsed_date:
                        date_str = parsed_date.date().strftime("%Y-%m-%d")
                        return {"start": date_str, "end": date_str}
                except Exception:
                    continue
            else:
                # Use fallback parsing
                groups = match.groups()
                if len(groups) >= 3:
                    try:
                        day = int(groups[0])
                        month_name = groups[1]
                        year = int(groups[2])
                        result = _parse_date_fallback(day, month_name, year)
                        if result:
                            return result
                    except Exception:
                        continue

    # patterns like "from X to Y" or "between X and Y"
    between_re = re.compile(r'(?:from|between)\s+([A-Za-z0-9,\s/-]+?)\s+(?:to|and)\s+([A-Za-z0-9,\s/-]+)', re.IGNORECASE)
    m = between_re.search(text)
    if m and HAS_DATEPARSER:
        s = dateparser.parse(m.group(1))
        e = dateparser.parse(m.group(2))
        if s and e:
            return {"start": s.date().strftime("%Y-%m-%d"), "end": e.date().strftime("%Y-%m-%d")}
    
    # if dateparser available, try to find any dates
    if HAS_DATEPARSER:
        try:
            found = dateparser.search.search_dates(text, settings={'PREFER_DATES_FROM': 'past'})
            if found:
                dates = [d[1].date() for d in found]
                if len(dates) == 1:
                    d = dates[0].strftime("%Y-%m-%d")
                    return {"start": d, "end": d}
                else:
                    s, e = min(dates), max(dates)
                    return {"start": s.strftime("%Y-%m-%d"), "end": e.strftime("%Y-%m-%d")}
        except Exception:
            pass

    return None


def extract_companions(text: str) -> Optional[List[str]]:
    """Enhanced companion extraction with multiple patterns"""
    companions = []
    
    # Pattern 1: "with Alice", "with Alice and Bob", "with Alice, Bob"
    pattern1 = re.compile(r'\bwith\s+([A-Za-z][A-Za-z\'\.\s,&-]+)', re.IGNORECASE)
    match1 = pattern1.search(text)
    if match1:
        tail = match1.group(1).strip()
        parts = re.split(r',| and | & | and ', tail)
        for p in parts:
            name = p.strip()
            if len(name) > 0 and len(name) < 60 and not re.search(r'\b(?:spent|rupee|rs|paid|via|on|for)\b', name, re.IGNORECASE):
                companions.append(name)
    
    # Pattern 2: "me and Alice", "Alice and me"
    pattern2 = re.compile(r'\b(?:me\s+and\s+([A-Za-z][A-Za-z\'\.\s-]+)|([A-Za-z][A-Za-z\'\.\s-]+)\s+and\s+me)\b', re.IGNORECASE)
    match2 = pattern2.search(text)
    if match2:
        name = match2.group(1) or match2.group(2)
        if name and len(name.strip()) < 60:
            companions.append(name.strip())
    
    # Pattern 3: "Alice, Bob, and me" or "Alice, Bob, me"
    pattern3 = re.compile(r'\b([A-Za-z][A-Za-z\'\.\s-]+(?:,\s*[A-Za-z][A-Za-z\'\.\s-]+)*)(?:\s*,\s*me|\s+and\s+me)\b', re.IGNORECASE)
    match3 = pattern3.search(text)
    if match3:
        names_str = match3.group(1)
        names = [name.strip() for name in names_str.split(',')]
        companions.extend([name for name in names if len(name) < 60])
    
    # Remove duplicates and clean up
    unique_companions = []
    for comp in companions:
        comp = comp.strip()
        if comp and comp not in unique_companions and len(comp) > 0:
            unique_companions.append(comp)
    
    return unique_companions or None


def extract_payment_methods(text: str) -> Optional[List[str]]:
    found = []
    text_lower = text.lower()
    for tok in PAYMENT_TOKENS:
        if tok in text_lower:
            found.append(tok)
    return found or None


def extract_candidate_categories(text: str) -> Optional[List[str]]:
    """Enhanced category extraction with priority-based selection"""
    found_categories = []
    text_lower = text.lower()
    
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                found_categories.append(cat)
                break  # Only add category once
    
    if not found_categories:
        return None
    
    # Sort by priority (lower number = higher priority)
    found_categories.sort(key=lambda x: CATEGORY_PRIORITY.get(x, 999))
    return found_categories


def pre_parse(text: str) -> Dict[str, Any]:
    """
    Enhanced pre-parsing with better entity extraction
    """
    amounts = extract_amounts(text)
    date_range = extract_date_range(text)
    companions = extract_companions(text)
    payment_methods = extract_payment_methods(text)
    candidate_categories = extract_candidate_categories(text)

    min_amount = None
    max_amount = None
    if amounts:
        # Enhanced heuristics for ranges
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
        "date_range": date_range,
        "companions": companions,
        "payment_methods": payment_methods,
        "candidate_categories": candidate_categories,
        "raw_text": text
    }
