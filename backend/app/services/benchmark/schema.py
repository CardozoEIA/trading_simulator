from pydantic import BaseModel


class BuyAndHoldSummary(BaseModel):
    initial_capital: float
    final_capital: float
    profit_loss: float
    total_return_pct: float