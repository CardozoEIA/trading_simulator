from datetime import date

import pytest

from app.services.benchmark.calculator import calculate_buy_and_hold
from app.services.historical_data.schema import Candle


def test_calculate_buy_and_hold_positive_return():
    candles = [
        Candle(
            date=date(2024, 1, 1),
            open=100,
            high=100,
            low=100,
            close=100,
            volume=1000
        ),
        Candle(
            date=date(2024, 1, 2),
            open=120,
            high=120,
            low=120,
            close=120,
            volume=1000
        ),
    ]

    result = calculate_buy_and_hold(
        candles=candles,
        initial_capital=1000
    )

    assert result.initial_capital == 1000
    assert result.final_capital == 1200
    assert result.profit_loss == 200
    assert result.total_return_pct == 20


def test_calculate_buy_and_hold_single_candle():
    candles = [
        Candle(
            date=date(2024, 1, 1),
            open=100,
            high=100,
            low=100,
            close=100,
            volume=1000
        )
    ]

    result = calculate_buy_and_hold(
        candles=candles,
        initial_capital=1000
    )

    assert result.initial_capital == 1000
    assert result.final_capital == 1000
    assert result.profit_loss == 0
    assert result.total_return_pct == 0


def test_calculate_buy_and_hold_raises_for_empty_candles():
    with pytest.raises(ValueError):
        calculate_buy_and_hold(
            candles=[],
            initial_capital=1000
        )


def test_calculate_buy_and_hold_raises_for_non_positive_initial_capital():
    candles = [
        Candle(
            date=date(2024, 1, 1),
            open=100,
            high=100,
            low=100,
            close=100,
            volume=1000
        )
    ]

    with pytest.raises(ValueError):
        calculate_buy_and_hold(
            candles=candles,
            initial_capital=0
        )