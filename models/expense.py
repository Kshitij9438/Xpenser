# models/expense.py
from pydantic import BaseModel, Field
from datetime import datetime

class Expenses(BaseModel):
    amount: float = Field(..., ge=0, description="The amount of the expense")
    date: datetime = Field(..., description="The date of the expense")
    companions: list[str] = Field(..., description="The companions of the expense")
    description: str = Field(..., description="The description of the expense")
    category: str = Field(..., description="The category of the expense")
    subcategory: str = Field(..., description="The sub-category of the expense")
    paymentMethod: str | None = Field(None, description="The payment method")
