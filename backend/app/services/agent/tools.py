# app/services/agent/tools.py
from langchain_core.tools import tool
from app.core.supabase import supabase_admin as supabase


def build_tools(simulation_id: str, user_id: str):

    @tool
    def get_price(date: str) -> str:
        """Get the closing price of the asset on a given date (YYYY-MM-DD)."""
        response = (
            supabase.table("simulation_signals")
            .select("price")
            .eq("simulation_id", simulation_id)
            .eq("date", date)
            .limit(1)
            .execute()
        )
        if not response.data:
            return f"No price data found for {date}."
        return f"Closing price on {date}: ${response.data[0]['price']:.2f}"

    @tool
    def get_decision(date: str) -> str:
        """Get the trading decision (BUY/SELL/HOLD) made on a given date, including
        whether it was executed and why, plus any rejection reason."""
        response = (
            supabase.table("simulation_decisions")
            .select("*")
            .eq("simulation_id", simulation_id)
            .eq("date", date)
            .limit(1)
            .execute()
        )
        if not response.data:
            return f"No decision found for {date}."
        d = response.data[0]
        parts = [f"Action: {d['action']}", f"Reason: {d['reason']}", f"Executed: {d['executed']}"]
        if d.get("rejection_reason"):
            parts.append(f"Rejection reason: {d['rejection_reason']}")
        return " | ".join(parts)

    @tool
    def get_indicators(date: str) -> str:
        """Get technical indicator values (SMA short/long, RSI, Bollinger bands, momentum)
        for a given date."""
        response = (
            supabase.table("simulation_signals")
            .select("*")
            .eq("simulation_id", simulation_id)
            .eq("date", date)
            .limit(1)
            .execute()
        )
        if not response.data:
            return f"No indicator data found for {date}."
        s = response.data[0]
        return (
            f"SMA short: {s['sma_short']}, SMA long: {s['sma_long']}, "
            f"RSI: {s['rsi']}, Bollinger bands: [{s['bollinger_lower']}, {s['bollinger_upper']}], "
            f"Momentum: {s['momentum']}"
        )

    @tool
    def get_risk_config() -> str:
        """Get the risk management configuration (stop-loss, max position size, max drawdown)
        used in this simulation."""
        response = (
            supabase.table("simulations")
            .select("configuration_id")
            .eq("id", simulation_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return "Simulation not found."
        config_id = response.data[0]["configuration_id"]
        risk = (
            supabase.table("risk_configurations")
            .select("*")
            .eq("configuration_id", config_id)
            .limit(1)
            .execute()
        )
        if not risk.data:
            return "No risk configuration found."
        r = risk.data[0]
        return (
            f"Stop-loss: {r['stop_loss_percentage']}%, "
            f"Max position size: {r['max_position_size']}%, "
            f"Max drawdown: {r['max_drawdown']}%"
        )

    @tool
    def get_market_regime(date: str) -> str:
        """Get the market regime in effect on a given date (trending / range-bound / high volatility)."""
        return "Market regime detection is not available yet in this version of the system."

    return [get_price, get_decision, get_indicators, get_risk_config, get_market_regime]