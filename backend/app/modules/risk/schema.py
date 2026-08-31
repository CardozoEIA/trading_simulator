from pydantic import BaseModel


class RiskConfiguration(BaseModel):
    configuration_id: str
    stop_loss_percentage: float
    max_position_size: float
    max_drawdown: float


class RiskConfigurationResponse(BaseModel):
    id: str
    configuration_id: str
    stop_loss_percentage: float
    max_position_size: float
    max_drawdown: float