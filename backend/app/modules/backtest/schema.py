from datetime import date

from pydantic import BaseModel


class BacktestConfiguration(BaseModel):
    asset: str
    start_date: date
    end_date: date


class BacktestConfigurationResponse(BaseModel):
    id: str
    asset: str
    start_date: date
    end_date: date
    data_available: bool
    records: int