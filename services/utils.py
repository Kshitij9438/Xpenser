from datetime import datetime
from decimal import Decimal
from typing import Any

def deep_serialize(obj: Any) -> Any:
    """
    Recursively convert objects to JSON-safe primitives.
    """
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        try:
            return deep_serialize(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return deep_serialize(obj.dict())
        except Exception:
            pass
    if isinstance(obj, dict):
        return {k: deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [deep_serialize(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    try:
        return deep_serialize(obj.__dict__)
    except Exception:
        return str(obj)
