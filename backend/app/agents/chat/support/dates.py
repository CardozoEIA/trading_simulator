from app.core.supabase import supabase_admin as supabase


def load_decision_dates(simulation_id: str) -> list[str]:
    response = (
        supabase.table("simulation_decisions")
        .select("date")
        .eq("simulation_id", simulation_id)
        .order("date")
        .execute()
    )

    return [row["date"] for row in response.data]


def resolve_date(
    dates: list[str],
    last_date: str | None,
    day_number: int | None,
    offset: int | None,
    date: str | None,
) -> tuple[str | None, str | None]:
    """Return (resolved_date, error_message). Exactly one of the two is None."""

    # Rule 1: explicit day number
    if day_number is not None:
        if isinstance(day_number, bool) or not isinstance(day_number, int):
            return (None, "Day number must be an integer.")

        if day_number < 1 or day_number > len(dates):
            return (
                None,
                f"This simulation has {len(dates)} days. Day {day_number} is out of range."
            )

        return (dates[day_number - 1], None)

    # Rule 2: relative offset
    if offset is not None:
        if isinstance(offset, bool) or not isinstance(offset, int):
            return (None, "Offset must be an integer.")

        if last_date is None:
            return (
                None,
                "I don't know which day to move from. Please specify a day first."
            )

        if last_date not in dates:
            return (
                None,
                "The previously discussed day could not be found."
            )

        current_index = dates.index(last_date)
        target_index = current_index + offset

        if target_index < 0 or target_index >= len(dates):
            return (
                None,
                f"This simulation has {len(dates)} days. The requested day is out of range."
            )

        return (dates[target_index], None)

    # Rule 3: explicit date
    if date is not None:
        if date in dates:
            return (date, None)

        return (
            None,
            "That date is not part of this simulation."
        )

    # Rule 4: fallback
    return (
        None,
        "Could you tell me which day you mean?"
    )
