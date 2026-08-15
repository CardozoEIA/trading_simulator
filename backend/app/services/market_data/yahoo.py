import yfinance as yf


SP500_TICKER = "^GSPC"


def get_historical_data(
    start_date: str,
    end_date: str
):
    data = yf.download(
        SP500_TICKER,
        start=start_date,
        end=end_date,
        auto_adjust=False,
        progress=False
    )

    if data.empty:
        return None

    data = data.reset_index()

    data.columns = [
        column[0] if isinstance(column, tuple) else column
        for column in data.columns
    ]

    data = data.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        }
    )

    data = data[
        ["date", "open", "high", "low", "close", "volume"]
    ]

    return data