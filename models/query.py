# FILE: models/query.py
from pydantic import BaseModel, Field, validator
from typing import Any, Dict, List, Optional, Literal
from core.query_shape import QueryShape

# -----------------------------
# Date Range
# -----------------------------
class DateRange(BaseModel):
    start: Optional[str] = Field(
        None, description="Start date (inclusive), ISO format YYYY-MM-DD"
    )
    end: Optional[str] = Field(
        None, description="End date (inclusive), ISO format YYYY-MM-DD"
    )

# -----------------------------
# Query Filters
# -----------------------------
class QueryFilters(BaseModel):
    category: Optional[str] = Field(None)
    subcategory: Optional[str] = Field(None)
    companions: Optional[List[str]] = Field(None)
    paymentMethod: Optional[str] = Field(None)
    min_amount: Optional[float] = Field(None)
    max_amount: Optional[float] = Field(None)
    date_range: Optional[DateRange] = Field(None)
    extras: Optional[Dict[str, Any]] = Field(None)

# -----------------------------
# Query Request (Parser → Builder)
# -----------------------------
class QueryRequest(BaseModel):
    user_id: Any = Field(..., description="User making the query")
    filters: QueryFilters = Field(default_factory=QueryFilters)

    aggregate: Optional[Literal["sum", "avg", "count", "min", "max"]] = Field(None)
    aggregate_field: Optional[str] = Field("amount")

    group_by: Optional[List[str]] = Field(None)
    columns: Optional[List[str]] = Field(None)

    limit: int = Field(default=100)
    offset: int = Field(default=0)
    sort_by: Optional[str] = Field(None)
    sort_order: Optional[Literal["asc", "desc"]] = Field(default="desc")

    # 🔒 AUTHORITATIVE — MUST be resolved before execution
    shape: QueryShape = Field(
        ...,
        description="Resolved query shape; must be set before execution",
    )

    # -----------------------------
    # Validators
    # -----------------------------
    @validator("shape", pre=True, always=True)
    def shape_must_be_present(cls, v):
        if v is None:
            raise ValueError(
                "QueryRequest.shape is mandatory. "
                "Resolve query shape before execution."
            )
        return v

    @validator("aggregate_field")
    def check_aggregate_field(cls, v):
        if v == "companions":
            raise ValueError("Cannot aggregate on array field 'companions'")
        return v

    @validator("group_by", each_item=True)
    def check_group_by(cls, v):
        if v == "companions":
            raise ValueError("Cannot group by array field 'companions'")
        return v

    @validator("limit", pre=True, always=True)
    def default_limit(cls, v):
        return v if v and v > 0 else 100

    @validator("offset", pre=True, always=True)
    def default_offset(cls, v):
        return v if v and v >= 0 else 0

# -----------------------------
# Query Result (Builder → Answer Agent)
# -----------------------------
class QueryResult(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    aggregate_result: Optional[Dict[str, Any]] = Field(None)
    meta: Optional[Dict[str, Any]] = Field(default=None)

# -----------------------------
# NLP Response (Answer Agent → API)
# -----------------------------
class NLPResponse(BaseModel):
    user_id: Any
    answer: str
    query: Optional[QueryRequest] = None
    output: Optional[QueryResult] = None
    context: Optional[Dict[str, Any]] = None
