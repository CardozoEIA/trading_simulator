# app/agents/explain/tools.py
from langchain_core.tools import tool
from app.core.supabase import supabase_admin as supabase


REGIME_NAMES = {
    "HIGH_VOLATILITY": "high volatility",
    "TRENDING": "trending",
    "RANGE_BOUND": "range-bound",
}


def describe_regime(row: dict) -> str:
    """Plain-language text for the regime stored with a day's signals."""
    regime = row.get("regime")
    if not regime:
        return "No market regime is available for this date (there was not enough earlier history to classify it)."
    return (
        f"Market regime: {REGIME_NAMES.get(regime, regime)} "
        f"(classified by model {row.get('regime_model_version')}, trained only on earlier data)."
    )


def describe_breakdown(breakdown: dict | None) -> str:
    """Plain-language text for the ensemble breakdown stored with a decision (US-24)."""
    if not breakdown:
        return "This decision did not come from a combination of strategies (a single strategy was used)."
    lines = [
        f"Combined decision: {breakdown['decision']} | blended score {breakdown['blended_score']:+.3f} "
        f"| threshold {breakdown['threshold']} | market regime: "
        f"{REGIME_NAMES.get(breakdown['regime'], breakdown['regime'].lower())}"
    ]
    for item in breakdown["components"]:
        lines.append(
            f"- {item['strategy']}: signal {item['direction']}, score {item['score']:+.3f}, "
            f"weight {item['weight']:.2f}, contribution {item['contribution']:+.3f}"
        )
    return "\n".join(lines)


def reference_text(strategies: list[str], custom_snapshots: list[dict] | None, threshold: float | None) -> str:
    """The definition of the strategies a simulation used: parameters and score limits.
    These are settings, not claims about the data, so an explanation may quote them (US-31 verification)."""
    from app.services.strategy import custom as custom_module

    snapshots = {f"CUSTOM:{c['name']}": c for c in custom_snapshots or []}
    lines = []
    for name in strategies:
        if name in snapshots:
            base, params = snapshots[name]["base_strategy"], snapshots[name]["params"]
        elif name in custom_module.PARAMETERS:
            base, params = name, custom_module.default_parameters(name)
        else:
            continue
        values = ", ".join(f"{key} {value}" for key, value in params.items())
        lines.append(f"Strategy {name} ({base}) parameters: {values}")
    limit = threshold if threshold else 0.1
    lines.append(f"Score limits: BUY above {limit}, SELL below -{limit}")
    return "\n".join(lines)


def strategy_reference(simulation_id: str) -> str:
    simulation = (
        supabase.table("simulations").select("configuration_id").eq("id", simulation_id).limit(1).execute().data
    )
    if not simulation:
        return ""
    config = (
        supabase.table("backtest_configurations").select("*").eq("id", simulation[0]["configuration_id"])
        .limit(1).execute().data
    )
    if not config:
        return ""
    row = config[0]
    return reference_text(row["strategies"], row.get("custom_strategies"), row.get("ensemble_threshold"))


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
        """Get the market regime in effect on a given date (trending / range-bound / high volatility).
        The regime is context only: it never decides a BUY/SELL/HOLD on its own."""
        response = (
            supabase.table("simulation_signals")
            .select("regime, regime_model_version")
            .eq("simulation_id", simulation_id)
            .eq("date", date)
            .limit(1)
            .execute()
        )
        if not response.data:
            return f"No data found for {date}."
        return describe_regime(response.data[0])

    @tool
    def get_ensemble_breakdown(date: str) -> str:
        """When several strategies were combined, get how the combined decision of a given date was made:
        the market regime, and each strategy's signal, score and weight."""
        response = (
            supabase.table("simulation_decisions")
            .select("breakdown")
            .eq("simulation_id", simulation_id)
            .eq("date", date)
            .limit(1)
            .execute()
        )
        if not response.data:
            return f"No decision found for {date}."
        return describe_breakdown(response.data[0].get("breakdown"))

    return [get_price, get_decision, get_indicators, get_risk_config, get_market_regime, get_ensemble_breakdown]