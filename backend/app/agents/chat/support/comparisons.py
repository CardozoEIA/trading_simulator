"""Which simulation the student wants to compare the current one with (US-27).

Resolved by code from the student's own history; when it is ambiguous the student
is asked, with their recent simulations listed as a numbered menu.
"""
from app.agents.compare.tools import describe

MAX_LISTED = 5

NO_OTHER = "You don't have another finished simulation to compare this one with yet."


def _choices(history: list[dict], simulation_id: str) -> list[dict]:
    return [h for h in history if h["id"] != simulation_id and h["status"] != "RUNNING"][:MAX_LISTED]


def _menu(choices: list[dict]) -> str:
    lines = ["Which simulation should I compare this one with? Your recent simulations:"]
    for number, h in enumerate(choices, start=1):
        result = f"{h['total_return_pct']:+.2f}%" if h.get("total_return_pct") is not None else "no result"
        lines.append(f"{number}. {describe(h)} (return {result})")
    lines.append('Reply for example "compare with number 2".')
    return "\n".join(lines)


def resolve_comparison(
    history: list[dict],
    simulation_id: str,
    compare_with: str | None,
    simulation_number: int | None,
) -> tuple[str | None, str | None]:
    """Returns (other_simulation_id, None) or (None, message for the student)."""
    choices = _choices(history, simulation_id)
    if not choices:
        return None, NO_OTHER

    if simulation_number is not None:
        if 1 <= simulation_number <= len(choices):
            return choices[simulation_number - 1]["id"], None
        return None, f"There is no simulation number {simulation_number} in the list.\n" + _menu(choices)

    if compare_with == "previous":
        ids = [h["id"] for h in history]
        if simulation_id in ids:
            older = [h for h in history[ids.index(simulation_id) + 1:] if h["status"] != "RUNNING"]
            if older:
                return older[0]["id"], None
        return None, "This is your oldest simulation, so there is no previous one.\n" + _menu(choices)

    return None, _menu(choices)
