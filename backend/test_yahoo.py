from app.services.market_data.yahoo import get_historical_data


data = get_historical_data(
    "2024-01-01",
    "2024-01-10"
)

print(data)