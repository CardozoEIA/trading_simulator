from app.core.supabase import supabase_admin
from app.services.market_data.yahoo import get_historical_data


def load_historical_data(
    start_date: str,
    end_date: str
):
    data = get_historical_data(
        start_date,
        end_date
    )

    if data is None:
        return 0

    records = []

    for _, row in data.iterrows():
        records.append({
            "asset": "SP500",
            "date": row["date"].strftime("%Y-%m-%d"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"])
        })

    if not records:
        return 0

    response = (
        supabase_admin
        .table("historical_data")
        .upsert(
            records,
            on_conflict="asset,date"
        )
        .execute()
    )

    return len(response.data)