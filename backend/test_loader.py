from app.services.market_data.loader import load_historical_data


inserted = load_historical_data(
    "2024-01-01",
    "2024-01-10"
)

print(f"Registros procesados: {inserted}")