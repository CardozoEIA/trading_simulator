# app/modules/portfolio/schema.py
from datetime import date as date_type
from pydantic import BaseModel

class Trade(BaseModel):
    date: date_type
    type: str
    price: float
    quantity: float
    cash_after: float
    shares_after: float
    portfolio_value_after: float