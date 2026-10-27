# app/modules/regime/service.py
"""US-23: stores and reads market-regime labels."""
import logging
from datetime import date

from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase
from app.services.regime.classifier import MODEL_VERSION, Regime, RegimeLabel, build_regime_labels

logger = logging.getLogger(__name__)

WRITE_CHUNK = 500


def _to_row(asset: str, label: RegimeLabel) -> dict:
    return {
        "asset": asset,
        "date": label.date.isoformat(),
        "algorithm_version": MODEL_VERSION,
        "regime": label.regime.value,
        "volatility": label.volatility,
        "trend_strength": label.trend_strength,
        "checkpoint_date": label.checkpoint_date.isoformat(),
        "model_version": label.model_version,
    }


def _from_row(row: dict) -> RegimeLabel:
    return RegimeLabel(
        date=date.fromisoformat(row["date"]),
        regime=Regime(row["regime"]),
        volatility=row["volatility"],
        trend_strength=row["trend_strength"],
        checkpoint_date=date.fromisoformat(row["checkpoint_date"]),
        model_version=row["model_version"],
    )


def save_regime_labels(asset: str, labels: list[RegimeLabel]) -> int:
    """Upserts the labels (same asset + date + algorithm version = replaced). Returns how many were written."""
    rows = [_to_row(asset, label) for label in labels]
    try:
        for start in range(0, len(rows), WRITE_CHUNK):
            supabase.table("market_regimes").upsert(
                rows[start : start + WRITE_CHUNK], on_conflict="asset,date,algorithm_version"
            ).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save the market regime labels")
    return len(rows)


def load_regime_labels(asset: str, start: date, end: date) -> dict[date, RegimeLabel]:
    """Precalculated labels between two dates (inclusive), keyed by date."""
    try:
        rows = (
            supabase.table("market_regimes")
            .select("*")
            .eq("asset", asset)
            .eq("algorithm_version", MODEL_VERSION)
            .gte("date", start.isoformat())
            .lte("date", end.isoformat())
            .order("date")
            .execute()
        ).data
    except Exception:
        raise HTTPException(status_code=503, detail="Could not read the market regime labels")
    return {label.date: label for label in (_from_row(r) for r in rows)}


def regime_on_or_before(asset: str, target: date) -> RegimeLabel | None:
    """The label of `target`, or of the closest earlier trading day (weekends, holidays)."""
    try:
        rows = (
            supabase.table("market_regimes")
            .select("*")
            .eq("asset", asset)
            .eq("algorithm_version", MODEL_VERSION)
            .lte("date", target.isoformat())
            .order("date", desc=True)
            .limit(1)
            .execute()
        ).data
    except Exception:
        raise HTTPException(status_code=503, detail="Could not read the market regime labels")
    return _from_row(rows[0]) if rows else None


PAGE_SIZE = 1000  # Supabase returns at most 1000 rows per request


def load_full_history(asset: str, end: date) -> list:
    """Every valid candle of the asset up to `end`, read page by page (a long history exceeds one request)."""
    from app.services.historical_data.processor import _is_valid_candle
    from app.services.historical_data.schema import Candle

    candles, offset = [], 0
    try:
        while True:
            rows = (
                supabase.table("historical_data")
                .select("*")
                .eq("asset", asset)
                .lte("date", end.isoformat())
                .order("date")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            ).data
            candles.extend(Candle(**r) for r in rows if _is_valid_candle(r))
            if len(rows) < PAGE_SIZE:
                return candles
            offset += PAGE_SIZE
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Could not read the historical data")


def regimes_for_candles(asset: str, candles: list) -> dict[date, RegimeLabel]:
    """Labels for the days of a simulation. Uses the stored labels when they cover the period; otherwise
    recomputes them from the asset's full history up to the last day. The method is causal, so both
    routes give the same label for the same date. Never raises: a simulation runs without regimes."""
    if not candles:
        return {}
    first, last = candles[0].date, candles[-1].date
    try:
        stored = load_regime_labels(asset, first, last)
        if stored:
            return stored
    except HTTPException:
        logger.warning("Stored regime labels unavailable; recomputing")

    try:
        history = load_full_history(asset, last)
        return {label.date: label for label in build_regime_labels(history) if label.date >= first}
    except Exception:
        logger.exception("Could not compute regime labels; the simulation will run without them")
        return {}
