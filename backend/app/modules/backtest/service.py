from fastapi import HTTPException

from app.core.supabase import supabase
from app.modules.backtest.schema import BacktestConfiguration


AVAILABLE_ASSETS = {
    "SP500": "S&P 500"
}


def get_available_assets():
    return [
        {
            "symbol": symbol,
            "name": name
        }
        for symbol, name in AVAILABLE_ASSETS.items()
    ]


def validate_configuration(
    configuration: BacktestConfiguration,
    user_id: str
):
    if configuration.start_date >= configuration.end_date:
        raise HTTPException(
            status_code=400,
            detail="La fecha inicial debe ser anterior a la fecha final"
        )

    if configuration.asset not in AVAILABLE_ASSETS:
        raise HTTPException(
            status_code=400,
            detail="El activo seleccionado no está disponible"
        )

    response = (
        supabase
        .table("historical_data")
        .select("date")
        .eq("asset", configuration.asset)
        .gte("date", configuration.start_date.isoformat())
        .lte("date", configuration.end_date.isoformat())
        .execute()
    )

    records = len(response.data)

    if records == 0:
        raise HTTPException(
            status_code=404,
            detail="No existen datos para el período seleccionado"
        )

    configuration_data = {
        "user_id": user_id,
        "asset": configuration.asset,
        "start_date": configuration.start_date.isoformat(),
        "end_date": configuration.end_date.isoformat()
    }

    saved_configuration = (
        supabase
        .table("backtest_configurations")
        .insert(configuration_data)
        .execute()
    )

    if not saved_configuration.data:
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar la configuración"
        )

    saved = saved_configuration.data[0]

    return {
        "id": saved["id"],
        "asset": saved["asset"],
        "start_date": saved["start_date"],
        "end_date": saved["end_date"],
        "data_available": True,
        "records": records
    }