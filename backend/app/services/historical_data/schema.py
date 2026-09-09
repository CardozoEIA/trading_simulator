from datetime import date

from pydantic import BaseModel


class Candle(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class DataGap(BaseModel):
    gap_starts_after: date
    gap_ends_before: date
    days_missing: int


class ProcessedHistoricalData(BaseModel):
    asset: str
    candles: list[Candle]
    gaps: list[DataGap]
    total_records: int