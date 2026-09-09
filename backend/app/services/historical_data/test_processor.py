from app.services.historical_data.processor import _is_valid_candle, _detect_gaps


def test_valid_candle_passes():
    candle = {
        "open": 100,
        "high": 105,
        "low": 98,
        "close": 102,
        "volume": 1000
    }
    assert _is_valid_candle(candle) is True

def test_candle_with_high_below_low_fails():
    candle = {
        "open": 100,
        "high": 90,
        "low": 95,
        "close": 92,
        "volume": 1000
    }
    assert _is_valid_candle(candle) is False

def test_no_gap_for_normal_weekend():
    candles = [
        {"date": "2024-01-05"},  # Viernes
        {"date": "2024-01-08"}   # Lunes
    ]

    resultado = _detect_gaps(candles)

    assert resultado == []


def test_gap_detected_for_long_absence():
    candles = [
        {"date": "2024-01-05"},
        {"date": "2024-01-15"}
    ]

    resultado = _detect_gaps(candles)

    assert len(resultado) == 1