"""Validation of risk-limit proposals.

The agent only PROPOSES. Nothing is written anywhere: the student must confirm in the UI,
either to run the what-if (US-28) or to open the normal setup flow with the suggested value.
"""
from app.agents.whatif.plan import plan_steps

PARAMETERS = {
    "stop_loss_percentage": "stop-loss",
    "max_position_size": "max position size",
    "max_drawdown": "max drawdown",
}

ASK_AGAIN = "Which risk limit would you like to try, and with what value? For example: a 3% stop-loss."


def build_proposal(parameter, value, current: dict | None) -> tuple[dict | None, str | None]:
    """Return (proposal, error_message). Exactly one of the two is None."""

    if parameter not in PARAMETERS or value is None:
        return (None, ASK_AGAIN)

    if value <= 0 or value > 100:
        return (None, "A risk limit must be greater than 0% and at most 100%.")

    label = PARAMETERS[parameter]

    raw_current = (current or {}).get(parameter)
    current_value = float(raw_current) if raw_current is not None else None

    if current_value is not None and current_value == float(value):
        return (None, f"Your {label} is already {value:g}%.")

    proposal = {
        "parameter": parameter,
        "label": label,
        "current": current_value,
        "suggested": float(value),
    }

    return ({**proposal, "plan": plan_steps(proposal)}, None)


def proposal_message(proposal: dict) -> str:
    text = f"I can set up a new simulation with the {proposal['label']} at {proposal['suggested']:g}%"

    if proposal["current"] is not None:
        text += f" (it is {proposal['current']:g}% in this one)"

    return text + (
        ". This simulation will not change. Review the plan below and press Run what-if to run "
        "the copy and compare both, or open the setup with that value."
    )