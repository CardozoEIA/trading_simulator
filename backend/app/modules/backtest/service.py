from fastapi import HTTPException

from app.core.supabase import supabase
from app.modules.backtest.schema import BacktestConfiguration



AVAILABLE_ASSETS = {
    "SP500": "S&P 500"
}

AVAILABLE_STRATEGIES = {
    "SMA": "Moving Average Crossover",
    "RSI": "Relative Strength Index",
    "BOLLINGER": "Bollinger Bands"
}


def get_available_assets():
    return [{"symbol": s, "name": n} for s, n in AVAILABLE_ASSETS.items()]


def get_available_strategies():
    return [{"code": c, "name": n} for c, n in AVAILABLE_STRATEGIES.items()]


def validate_configuration(configuration: BacktestConfiguration) -> int:
    """Validates the configuration and returns the number of available records."""
    if configuration.start_date >= configuration.end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be earlier than end date"
        )

    if configuration.asset not in AVAILABLE_ASSETS:
        raise HTTPException(
            status_code=400,
            detail="The selected asset is not available"
        )

    try:
        response = (
            supabase
            .table("historical_data")
            .select("date", count="exact")
            .eq("asset", configuration.asset)
            .gte("date", configuration.start_date.isoformat())
            .lte("date", configuration.end_date.isoformat())
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if response.count == 0:
        raise HTTPException(
            status_code=404,
            detail="No data available for the selected period"
        )

    return response.count


def save_configuration(configuration: BacktestConfiguration, user_id: str, records: int) -> dict:
    """Persists a fully-validated configuration in a single write."""
    configuration_data = {
        "user_id": user_id,
        "asset": configuration.asset,
        "start_date": configuration.start_date.isoformat(),
        "end_date": configuration.end_date.isoformat(),
        "initial_capital": configuration.initial_capital,
        "strategy": configuration.strategy.value
    }

    try:
        saved_configuration = (
            supabase
            .table("backtest_configurations")
            .insert(configuration_data)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not saved_configuration.data:
        raise HTTPException(
            status_code=500,
            detail="Could not save the configuration"
        )

    saved = saved_configuration.data[0]

    return {
        "id": saved["id"],
        "asset": saved["asset"],
        "start_date": saved["start_date"],
        "end_date": saved["end_date"],
        "initial_capital": saved["initial_capital"],
        "strategy": saved["strategy"],
        "data_available": True,
        "records": records
    }