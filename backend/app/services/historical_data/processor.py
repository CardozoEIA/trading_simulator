from datetime import date

from app.core.supabase import supabase
from app.services.historical_data.schema import Candle, DataGap, ProcessedHistoricalData


def _fetch_candles(asset: str, start_date: date, end_date: date):
    response = (
        supabase
        .table("historical_data")
        .select("*")
        .eq("asset", asset)
        .gte("date", start_date.isoformat())
        .lte("date", end_date.isoformat())
        .order("date")
        .execute()
    )
    return response.data

def _is_valid_candle(candle: dict) -> bool:
    if candle["high"] < candle["low"]:
        return False
    if candle["high"] < candle["open"] or candle["high"] < candle["close"]:
        return False
    if candle["low"] > candle["open"] or candle["low"] > candle["close"]:
        return False
    if candle["open"] <= 0 or candle["close"] <= 0 or candle["high"] <= 0 or candle["low"] <= 0:
        return False
    return candle["volume"] >= 0

def _detect_gaps(candles: list[dict]) -> list[dict]:
    gaps = []
    for i in range(1, len(candles)):
        previous = candles[i - 1]
        current = candles[i]
        previous_date = date.fromisoformat(previous["date"])
        current_date = date.fromisoformat(current["date"])
        difference = (current_date - previous_date).days
        if difference > 5:
            gaps.append({ "gap_starts_after": previous_date, "gap_ends_before": current_date, "days_missing": difference - 1 })
    return gaps

def process_historical_data(asset: str, start_date: date, end_date: date) -> ProcessedHistoricalData:
    raw_candles = _fetch_candles(asset=asset, start_date=start_date, end_date=end_date)
    candles = [c for c in raw_candles if _is_valid_candle(c)]
    gaps = _detect_gaps(candles)
    total_records = len(candles)
    result = ProcessedHistoricalData(
        asset = asset,
        candles = [Candle(**c) for c in candles],
        gaps = [DataGap(**g) for g in gaps],
        total_records = total_records
    )
    return result