# app/modules/portfolio/service.py
from fastapi import HTTPException
from app.core.supabase import supabase_admin as supabase
from app.modules.portfolio.schema import Trade, EquityPoint
from app.services.strategy.schema import Decision, DecisionAction


class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.shares = 0.0

    def value(self, price: float) -> float:
        return self.cash + self.shares * price

    def apply_decision(self, decision: Decision, price: float, risk_manager=None) -> tuple[Trade | None, str | None, str | None]:
        """Devuelve (trade, rejection_reason, override_reason).
        override_reason se usa cuando el Risk Manager genera una acción que
        la estrategia no pidió (ej. stop-loss), para que quede registrada
        en simulation_decisions con su motivo real, no como el HOLD original."""

        # 1. Stop-loss: fuerza un SELL si la posición abierta cayó demasiado, sin importar la señal
        if risk_manager and self.shares > 0 and risk_manager.should_stop_loss(price):
            quantity = self.shares
            self.cash += quantity * price
            self.shares = 0.0
            risk_manager.entry_price = None
            trade = Trade(date=decision.date, type="SELL", price=price, quantity=quantity,
                          cash_after=self.cash, shares_after=self.shares,
                          portfolio_value_after=self.value(price))
            override_reason = f"Stop-loss triggered ({risk_manager.stop_loss_pct:.1%} below entry price)"
            return trade, None, override_reason

        # 2. Max drawdown: bloquea nuevas compras si ya se cayó demasiado desde el pico
        if risk_manager and decision.action == DecisionAction.BUY:
            drawdown = risk_manager.current_drawdown(self.value(price))
            if drawdown >= risk_manager.max_drawdown_pct:
                return None, f"Blocked BUY: drawdown {drawdown:.1%} reached max allowed {risk_manager.max_drawdown_pct:.1%}", None

        if decision.action == DecisionAction.BUY and self.cash > 0:
            # 3. Max position size: no invertir más del % configurado del valor total del portafolio
            max_investable = self.value(price) * (risk_manager.max_position_size_pct if risk_manager else 1.0)
            invest_amount = min(self.cash, max_investable)
            if invest_amount <= 0:
                return None, "Blocked BUY: max position size already reached", None
            quantity = invest_amount / price
            self.cash -= quantity * price
            self.shares += quantity
            if risk_manager:
                risk_manager.entry_price = price
        elif decision.action == DecisionAction.SELL and self.shares > 0:
            quantity = self.shares
            self.cash += quantity * price
            self.shares = 0.0
            if risk_manager:
                risk_manager.entry_price = None
        else:
            return None, None, None

        trade = Trade(date=decision.date, type=decision.action.value, price=price,
                      quantity=quantity, cash_after=self.cash, shares_after=self.shares,
                      portfolio_value_after=self.value(price))
        return trade, None, None


def run_portfolio(candles: list, decisions: list[Decision], initial_capital: float, risk_manager=None) -> tuple[list[Trade], list[EquityPoint], dict, dict]:
    portfolio = Portfolio(initial_capital=initial_capital)
    trades = []
    equity_curve = []
    rejections = {}
    overrides = {}

    for candle, decision in zip(candles, decisions):
        trade, rejection_reason, override_reason = portfolio.apply_decision(decision, price=candle.close, risk_manager=risk_manager)
        if trade:
            trades.append(trade)
        if rejection_reason:
            rejections[decision.date] = rejection_reason
        if override_reason:
            overrides[candle.date] = override_reason

        equity_curve.append(EquityPoint(
            date=candle.date, portfolio_value=portfolio.value(candle.close),
            cash=portfolio.cash, shares=portfolio.shares
        ))

    return trades, equity_curve, rejections, overrides


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


def save_equity_curve(simulation_id: str, equity_curve: list[EquityPoint]) -> None:
    if not equity_curve:
        return
    rows = [{"simulation_id": simulation_id, "date": e.date.isoformat(),
             "portfolio_value": e.portfolio_value, "cash": e.cash, "shares": e.shares}
            for e in equity_curve]
    try:
        supabase.table("simulation_equity_curve").insert(rows).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save equity curve")


def get_equity_curve(simulation_id: str, user_id: str) -> list[dict]:
    response = (
        supabase.table("simulation_equity_curve")
        .select("*, simulations!inner(user_id)")
        .eq("simulation_id", simulation_id)
        .eq("simulations.user_id", user_id)
        .order("date")
        .execute()
    )
    return response.data