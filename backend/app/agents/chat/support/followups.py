"""Suggested follow-up questions. Fixed text, so every suggestion is a question the router handles."""

OVERVIEW = "Give me an overview of this simulation"
BENCHMARK = "Did the strategy beat buy & hold?"
FIRST_DAY = "Explain the decision on day 1"
NEXT_DAY = "And the next day?"
PREVIOUS_DAY = "And the previous day?"

DEFAULTS = [OVERVIEW, BENCHMARK, FIRST_DAY]


def suggest_followups(route: str | None, date: str | None = None) -> list[str]:
    if route == "explain_agent" and date:
        return [NEXT_DAY, PREVIOUS_DAY, BENCHMARK]

    if route == "insights_agent":
        return [BENCHMARK, FIRST_DAY, "What is max drawdown?"]

    if route == "answer":
        return [OVERVIEW, "What is buy & hold?", FIRST_DAY]

    if route == "conceptual":
        return [OVERVIEW, BENCHMARK, FIRST_DAY]

    if route == "compare":
        return [OVERVIEW, BENCHMARK, "What is the Sharpe ratio?"]

    if route == "propose_change":
        return [OVERVIEW, BENCHMARK, "What is a stop-loss?"]

    return list(DEFAULTS)