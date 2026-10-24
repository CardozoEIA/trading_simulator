# app/agents/whatif/plan.py
"""Planning and qualitative fallback of a what-if (US-28). Fixed text written by code."""

SUPPORTED_PARAMETERS = ("stop_loss_percentage", "max_position_size", "max_drawdown")


def plan_steps(proposal: dict) -> list[str]:
    """The ordered steps shown to the student before they confirm the what-if."""
    return [
        "Read the current configuration of this simulation",
        f"Run a copy with the {proposal['label']} at {proposal['suggested']:g}% (this simulation is not changed)",
        "Compare both runs",
    ]


# (parameter, the new value is lower) -> expected effect, in words only
_EFFECTS = {
    ("stop_loss_percentage", True): (
        "A tighter stop-loss closes losing trades sooner. That usually keeps each loss smaller, "
        "but it can also close trades that would have recovered, so the total result can go either way."
    ),
    ("stop_loss_percentage", False): (
        "A looser stop-loss gives trades more room before they are closed. Trades that recover can end "
        "with a gain, but the trades that keep falling lose more before the stop is reached."
    ),
    ("max_position_size", True): (
        "A smaller maximum position puts less of the portfolio into each trade. Gains and losses both "
        "become smaller, so the run is usually calmer but also grows more slowly."
    ),
    ("max_position_size", False): (
        "A larger maximum position puts more of the portfolio into each trade. Gains and losses both "
        "become larger, so the result depends more on how good each trade is."
    ),
    ("max_drawdown", True): (
        "A lower maximum drawdown makes the risk manager stop the run earlier after a fall. It protects "
        "the capital from deep drops, but the run may stop before it has a chance to recover."
    ),
    ("max_drawdown", False): (
        "A higher maximum drawdown lets the run continue through deeper falls. It has more time to "
        "recover, but it can also lose more before the risk manager stops it."
    ),
}


def expected_effect(parameter: str, current: float | None, suggested: float) -> str:
    """Qualitative explanation used when the re-run fails or is too slow. Contains no numbers."""
    lower = current is None or suggested < current
    return (
        "This is a general explanation of the expected effect, not a simulation result. "
        + _EFFECTS[(parameter, lower)]
    )
