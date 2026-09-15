# app/services/portfolio/engine.py
from app.services.strategy.schema import Decision, DecisionAction
from app.modules.portfolio.schema import Trade


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
    """candles[i] y decisions[i] están alineados por índice (garantizado por run_strategy)."""
    portfolio = Portfolio(initial_capital=initial_capital)
    trades = []
    for candle, decision in zip(candles, decisions):
        trade = portfolio.apply_decision(decision, price=candle.close)
        if trade:
            trades.append(trade)
    return trades