from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase
from app.modules.backtest.schema import BacktestConfiguration
from app.modules.custom_strategies.service import list_custom_strategies, resolve_for_configuration
from app.services.strategy.custom import describe as describe_custom
from app.services.strategy.factory import CUSTOM_PREFIX, custom_label


AVAILABLE_ASSETS = {
    "SP500": "S&P 500"
}

AVAILABLE_STRATEGIES = {
    "SMA": {
        "name": "Moving Average Crossover",
        "description": (
            "Buys when a short-term average of the price rises above a "
            "long-term average, and sells when it falls below it. It is "
            "used to follow the general trend of the market."
        )
    },
    "RSI": {
        "name": "Relative Strength Index",
        "description": (
            "Measures how fast and how much the price has moved recently. "
            "It buys when the asset looks oversold and sells when it looks "
            "overbought, aiming to catch short-term reversals."
        )
    },
    "BOLLINGER": {
        "name": "Bollinger Bands",
        "description": (
            "Draws a price band based on recent volatility. It buys when "
            "the price touches the lower band and sells when it touches "
            "the upper band, betting that prices tend to return to their "
            "average."
        )
    },
    "MOMENTUM": {
        "name": "Momentum",
        "description": (
            "Compares the current price against its price from several "
            "days ago. It buys when the price has been climbing steadily "
            "and sells when it has been falling, betting that a moving "
            "market keeps moving in the same direction."
        )
    }
}


def get_available_strategies(user_id: str | None = None):
    """The built-in strategies, followed by the student's custom ones (US-21), whose code is CUSTOM:<id>."""
    strategies = [
        {
            "code": code,
            "name": data["name"],
            "description": data["description"],
            "custom": False,
        }
        for code, data in AVAILABLE_STRATEGIES.items()
    ]
    if user_id:
        try:
            mine = list_custom_strategies(user_id)
        except HTTPException:
            mine = []  # the built-in list is still useful when the custom ones cannot be read
        strategies.extend(
            {
                "code": f"{CUSTOM_PREFIX}{row['id']}",
                "name": row["name"],
                "description": describe_custom(row["base_strategy"], row["params"]),
                "custom": True,
            }
            for row in sorted(mine, key=lambda r: r["name"].lower())
        )
    return strategies


def get_available_assets():
    return [{"symbol": s, "name": n} for s, n in AVAILABLE_ASSETS.items()]


MAX_STRATEGIES = 8
MAX_ENSEMBLE_THRESHOLD = 1.0


def validate_configuration(configuration: BacktestConfiguration, user_id: str | None = None) -> int:
    """Validates the configuration and returns the number of available records.
    `user_id` is needed to check custom strategies (US-21): they must exist and belong to the student."""
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

    total_strategies = len(configuration.strategies) + len(set(configuration.custom_strategy_ids))
    if total_strategies == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one strategy must be selected"
        )

    if total_strategies > MAX_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_STRATEGIES} strategies can be combined"
        )

    if len(set(configuration.strategies)) != len(configuration.strategies):
        raise HTTPException(
            status_code=400,
            detail="A strategy was selected more than once"
        )

    threshold = configuration.ensemble_threshold
    if threshold is not None and not 0 < threshold <= MAX_ENSEMBLE_THRESHOLD:
        raise HTTPException(
            status_code=400,
            detail=f"The ensemble threshold must be greater than 0 and at most {MAX_ENSEMBLE_THRESHOLD:g}"
        )

    if configuration.custom_strategy_ids:
        if user_id is None:
            raise HTTPException(
                status_code=400,
                detail="Custom strategies can only be used by a signed-in student"
            )
        resolve_for_configuration(configuration.custom_strategy_ids, user_id)  # 404 when missing or not owned

    for strategy in configuration.strategies:
        if strategy.value not in AVAILABLE_STRATEGIES:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy {strategy.value} is not available"
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
    except Exception as e:
        print("ERROR REAL en validate_configuration:", repr(e))
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


def save_configuration(configuration: BacktestConfiguration, user_id: str, records: int,
                       custom_snapshots: list[dict] | None = None) -> dict:
    """Persists a fully-validated configuration in a single write.

    Custom strategies are stored as a snapshot (US-21), so the simulation never changes if the student later
    edits or deletes the strategy. `custom_snapshots` lets a copy of a configuration (what-if) reuse them."""
    if custom_snapshots is None:
        custom_snapshots = resolve_for_configuration(configuration.custom_strategy_ids, user_id)

    configuration_data = {
        "user_id": user_id,
        "asset": configuration.asset,
        "start_date": configuration.start_date.isoformat(),
        "end_date": configuration.end_date.isoformat(),
        "initial_capital": configuration.initial_capital,
        "strategies": [s.value for s in configuration.strategies] + [custom_label(c["name"]) for c in custom_snapshots],
    }
    if custom_snapshots:
        configuration_data["custom_strategies"] = custom_snapshots
    if configuration.ensemble_threshold is not None:
        configuration_data["ensemble_threshold"] = configuration.ensemble_threshold

    try:
        saved_configuration = (
            supabase
            .table("backtest_configurations")
            .insert(configuration_data)
            .execute()
        )
    except Exception as e:
        print("ERROR REAL en validate_configuration:", repr(e))
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
        "strategies": saved["strategies"],
        "ensemble_threshold": saved.get("ensemble_threshold"),
        "data_available": True,
        "records": records
    }