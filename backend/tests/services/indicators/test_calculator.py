from app.services.indicators.calculator import calculate_all, _sma, _rsi, _bollinger, _momentum


class FakeCandle:
    def __init__(self, date, close):
        self.date = date
        self.close = close


def _make_candles(closes: list[float]) -> list[FakeCandle]:
    return [FakeCandle(date=f"2024-01-{i+1:02d}", close=c) for i, c in enumerate(closes)]


def test_sma_returns_none_before_enough_data():
    candles = _make_candles([100, 101, 102])
    assert _sma(candles, current_index=1, period=5) is None


def test_sma_calculates_average_of_window():
    candles = _make_candles([10, 20, 30, 40, 50])
    result = _sma(candles, current_index=4, period=5)
    assert result == 30.0


def test_rsi_returns_100_when_no_losses():
    candles = _make_candles([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114])
    result = _rsi(candles, current_index=14, period=14)
    assert result == 100.0


def test_bollinger_bands_are_symmetric_around_mean():
    candles = _make_candles([100, 102, 98, 101, 99, 100, 103, 97, 100, 102,
                              99, 101, 100, 98, 102, 100, 99, 101, 100, 102])
    mean, upper, lower = _bollinger(candles, current_index=19, period=20, num_std=2)
    assert upper - mean == mean - lower


def test_momentum_positive_when_price_increased():
    candles = _make_candles([100] * 10 + [110])
    result = _momentum(candles, current_index=10, period=10)
    assert result == 0.10


def test_calculate_all_returns_one_snapshot_per_candle():
    candles = _make_candles([100 + i for i in range(30)])
    snapshots = calculate_all(candles)
    assert len(snapshots) == 30
    assert snapshots[0].sma_short is None
    assert snapshots[29].sma_short is not None