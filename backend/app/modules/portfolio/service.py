# app/modules/portfolio/service.py
from fastapi import HTTPException
from app.core.supabase import supabase_admin as supabase
from app.modules.portfolio.schema import Trade
from app.services.strategy.schema import Decision, DecisionAction


class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.shares = 0.0

    def value(self, price: float) -> float:
        return self.cash + self.shares * price

    def apply_decision(self, decision: Decision, price: float) -> Trade | None:
        if decision.action == DecisionAction.BUY and self.cash > 0:
            quantity = self.cash / price
            self.cash -= quantity * price
            self.shares += quantity
        elif decision.action == DecisionAction.SELL and self.shares > 0:
            quantity = self.shares
            self.cash += quantity * price
            self.shares = 0.0
        else:
            return None

        return Trade(
            date=decision.date, type=decision.action.value, price=price,
            quantity=quantity, cash_after=self.cash, shares_after=self.shares,
            portfolio_value_after=self.value(price)
        )


def run_portfolio(candles: list, decisions: list[Decision], initial_capital: float) -> list[Trade]:
    portfolio = Portfolio(initial_capital=initial_capital)
    trades = []
    for candle, decision in zip(candles, decisions):
        trade = portfolio.apply_decision(decision, price=candle.close)
        if trade:
            trades.append(trade)
    return trades


def save_trades(simulation_id: str, trades: list[Trade]) -> None:
    if not trades:
        return
    rows = [{"simulation_id": simulation_id, "date": t.date.isoformat(), "type": t.type,
             "price": t.price, "quantity": t.quantity, "cash_after": t.cash_after,
             "shares_after": t.shares_after, "portfolio_value_after": t.portfolio_value_after}
            for t in trades]
    try:
        supabase.table("simulation_trades").insert(rows).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save simulated trades")


def get_trades(simulation_id: str, user_id: str) -> list[dict]:
    response = (
        supabase.table("simulation_trades")
        .select("*, simulations!inner(user_id)")
        .eq("simulation_id", simulation_id)
        .eq("simulations.user_id", user_id)
        .order("date")
        .execute()
    )
    return response.data