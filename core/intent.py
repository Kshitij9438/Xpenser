# core/intent.py
from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any


class Intent(BaseModel):
    """
    A passive container that represents what the user wants.
    This does NOT execute logic.
    This does NOT make decisions.
    """

    user_id: str
    raw_input: str

    # Decided by router_agent (single authority for now)
    type: Literal["expense", "query", "conversation"]

    # Optional metadata for later phases
    meta: Optional[Dict[str, Any]] = None
