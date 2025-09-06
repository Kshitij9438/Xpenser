# models/expense.py
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Union

class Expenses(BaseModel):
    amount: float = Field(..., ge=0, description="The amount of the expense")
    date: Union[datetime, str] = Field(..., description="The date of the expense")
    companions: list[str] = Field(default_factory=list, description="The companions of the expense")
    description: str = Field(default="", description="The description of the expense")
    category: str = Field(default="Other", description="The category of the expense")
    subcategory: str = Field(default="", description="The sub-category of the expense")
    paymentMethod: str | None = Field(None, description="The payment method")
    
    @field_validator('date')
    @classmethod
    def validate_date(cls, v):
        if isinstance(v, str):
            try:
                # Try to parse common date formats
                from dateutil import parser
                return parser.parse(v)
            except:
                # If parsing fails, use today's date
                return datetime.now()
        return v
    
    @field_validator('companions')
    @classmethod
    def validate_companions(cls, v):
        if not v:
            return []
        return v
