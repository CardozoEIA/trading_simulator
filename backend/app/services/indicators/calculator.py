# app/services/indicators/calculator.py
import statistics
from pydantic import BaseModel
from datetime import date as date_type

SMA_SHORT_PERIOD = 5
SMA_LONG_PERIOD = 20
RSI_PERIOD = 14
BOLLINGER_PERIOD = 20
BOLLINGER_NUM_STD = 2
MOMENTUM_PERIOD = 10


class IndicatorSnapshot(BaseModel):
    date: date_type
    price: float
    sma_short: float | None
    sma_long: float | None
    rsi: float | None
    bollinger_mean: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    momentum: float | None


def _sma(candles: list, current_index: int, period: int) -> float | None:
    if current_index + 1 < period:
        return None
    window = candles[current_index - period + 1: current_index + 1]
    return sum(c.close for c in window) / period


def _rsi(candles: list, current_index: int, period: int) -> float | None:
    if current_index + 1 < period + 1:
        return None
    window = candles[current_index - period: current_index + 1]
    gains, losses = [], []
    for i in range(1, len(window)):
        change = window[i].close - window[i - 1].close
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _bollinger(candles: list, current_index: int, period: int, num_std: float):
    if current_index + 1 < period:
        return None, None, None
    window = candles[current_index - period + 1: current_index + 1]
    closes = [c.close for c in window]
    mean = sum(closes) / period
    std_dev = statistics.pstdev(closes)
    return mean, mean + num_std * std_dev, mean - num_std * std_dev


def _momentum(candles: list, current_index: int, period: int) -> float | None:
    if current_index - period < 0:
        return None
    past_close = candles[current_index - period].close
    current_close = candles[current_index].close
    return (current_close - past_close) / past_close


def calculate_all(candles: list) -> list[IndicatorSnapshot]:
    """Calcula el set completo de indicadores técnicos para cada día del histórico,
    independientemente de qué estrategia(s) haya seleccionado el usuario."""
    snapshots = []
    for i, candle in enumerate(candles):
        mean, upper, lower = _bollinger(candles, i, BOLLINGER_PERIOD, BOLLINGER_NUM_STD)
        snapshots.append(IndicatorSnapshot(
            date=candle.date,
            price=candle.close,
            sma_short=_sma(candles, i, SMA_SHORT_PERIOD),
            sma_long=_sma(candles, i, SMA_LONG_PERIOD),
            rsi=_rsi(candles, i, RSI_PERIOD),
            bollinger_mean=mean,
            bollinger_upper=upper,
            bollinger_lower=lower,
            momentum=_momentum(candles, i, MOMENTUM_PERIOD)
        ))
    return snapshots