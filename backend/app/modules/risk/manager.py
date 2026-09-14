# app/modules/risk/manager.py
class RiskManager:
    def __init__(self, stop_loss_percentage: float, max_position_size: float, max_drawdown: float):
        self.stop_loss_pct = stop_loss_percentage / 100
        self.max_position_size_pct = max_position_size / 100
        self.max_drawdown_pct = max_drawdown / 100
        self.entry_price: float | None = None
        self.peak_value: float | None = None

    def current_drawdown(self, portfolio_value: float) -> float:
        if self.peak_value is None or portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
        if not self.peak_value:
            return 0.0
        return (self.peak_value - portfolio_value) / self.peak_value

    def should_stop_loss(self, price: float) -> bool:
        if self.entry_price is None:
            return False
        loss_pct = (price - self.entry_price) / self.entry_price
        return loss_pct <= -self.stop_loss_pct