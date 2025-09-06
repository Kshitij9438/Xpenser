"""
Date Resolver Service

- Converts natural language time expressions into concrete dates or ranges
- Prevents hallucination by grounding all relative references to real calendar values
"""

from datetime import date, timedelta, datetime
import calendar
from typing import Dict, Optional, Tuple


def get_today() -> date:
    """Return today's date (system clock)."""
    return date.today()


def resolve_date_range(text: str) -> Optional[Tuple[date, date]]:
    """
    Resolve natural language date expressions into (start_date, end_date).
    Returns None if no recognized pattern is found.
    """
    text = text.lower().strip()
    today = get_today()

    if text in ("today", "current day"):
        return today, today

    if text == "yesterday":
        d = today - timedelta(days=1)
        return d, d

    if text in ("this week", "current week"):
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)  # Sunday
        return start, min(end, today)

    if text in ("last week", "previous week"):
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return start, end

    if text in ("this month", "current month"):
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
        return start, min(end, today)

    if text in ("last month", "previous month"):
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, end

    return None


def resolve_expression(expr: str) -> Dict[str, str]:
    """
    High-level resolver.
    Returns a dict with start_date and end_date (ISO format) if matched,
    else returns an empty dict.
    """
    result = resolve_date_range(expr)
    if result:
        start, end = result
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
    return {}
