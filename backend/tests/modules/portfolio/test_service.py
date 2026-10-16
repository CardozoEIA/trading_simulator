from datetime import date

from app.modules.portfolio.service import run_portfolio
from app.modules.risk.manager import RiskManager
from app.services.historical_data.schema import Candle
from app.services.strategy.schema import Decision, DecisionAction


def test_run_portfolio_stops_on_max_drawdown():
    candles = [
        Candle(date=date(2024, 1, 1), open=100, high=100, low=100, close=100, volume=1000),
        Candle(date=date(2024, 1, 2), open=99, high=99, low=99, close=99, volume=1000),
        Candle(date=date(2024, 1, 3), open=97, high=97, low=97, close=97, volume=1000),
        Candle(date=date(2024, 1, 4), open=90, high=90, low=90, close=90, volume=1000),
        Candle(date=date(2024, 1, 5), open=85, high=85, low=85, close=85, volume=1000),
    ]

    decisions = [
        Decision(date=candles[0].date, action=DecisionAction.BUY, reason="entry"),
        Decision(date=candles[1].date, action=DecisionAction.HOLD, reason="hold"),
        Decision(date=candles[2].date, action=DecisionAction.HOLD, reason="hold"),
        Decision(date=candles[3].date, action=DecisionAction.HOLD, reason="hold"),
        Decision(date=candles[4].date, action=DecisionAction.HOLD, reason="hold"),
    ]

    risk_manager = RiskManager(
        stop_loss_percentage=50,
        max_position_size=100,
        max_drawdown=2,
    )

    trades, equity_curve, rejections, overrides, stop_reason = run_portfolio(
        candles=candles,
        decisions=decisions,
        initial_capital=10000,
        risk_manager=risk_manager,
    )

    assert stop_reason is not None
    assert len(equity_curve) < len(candles)


def test_run_portfolio_completes_when_drawdown_not_reached():
    candles = [
        Candle(date=date(2024, 1, 1), open=100, high=100, low=100, close=100, volume=1000),
        Candle(date=date(2024, 1, 2), open=100, high=100, low=100, close=100, volume=1000),
        Candle(date=date(2024, 1, 3), open=100, high=100, low=100, close=100, volume=1000),
        Candle(date=date(2024, 1, 4), open=100, high=100, low=100, close=100, volume=1000),
        Candle(date=date(2024, 1, 5), open=100, high=100, low=100, close=100, volume=1000),
    ]

    decisions = [
        Decision(date=candles[0].date, action=DecisionAction.BUY, reason="entry"),
        Decision(date=candles[1].date, action=DecisionAction.HOLD, reason="hold"),
        Decision(date=candles[2].date, action=DecisionAction.HOLD, reason="hold"),
        Decision(date=candles[3].date, action=DecisionAction.HOLD, reason="hold"),
        Decision(date=candles[4].date, action=DecisionAction.HOLD, reason="hold"),
    ]

    risk_manager = RiskManager(
        stop_loss_percentage=50,
        max_position_size=100,
        max_drawdown=2,
    )

    trades, equity_curve, rejections, overrides, stop_reason = run_portfolio(
        candles=candles,
        decisions=decisions,
        initial_capital=10000,
        risk_manager=risk_manager,
    )

    assert stop_reason is None
    assert len(equity_curve) == len(candles)