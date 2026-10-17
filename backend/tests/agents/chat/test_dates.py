from app.agents.chat.support.dates import resolve_date


DATES = [
    "2024-01-02",
    "2024-01-03",
    "2024-01-04",
]


def test_day_number_returns_second_date():
    resolved, error = resolve_date(
        DATES,
        last_date=None,
        day_number=2,
        offset=None,
        date=None,
    )

    assert resolved == "2024-01-03"
    assert error is None


def test_day_number_out_of_range():
    resolved, error = resolve_date(
        DATES,
        last_date=None,
        day_number=4,
        offset=None,
        date=None,
    )

    assert resolved is None
    assert "3" in error


def test_offset_plus_one_returns_next_date():
    resolved, error = resolve_date(
        DATES,
        last_date="2024-01-03",
        day_number=None,
        offset=1,
        date=None,
    )

    assert resolved == "2024-01-04"
    assert error is None


def test_offset_past_last_date_returns_error():
    resolved, error = resolve_date(
        DATES,
        last_date="2024-01-04",
        day_number=None,
        offset=1,
        date=None,
    )

    assert resolved is None
    assert error is not None


def test_offset_without_last_date_returns_error():
    resolved, error = resolve_date(
        DATES,
        last_date=None,
        day_number=None,
        offset=1,
        date=None,
    )

    assert resolved is None
    assert error is not None


def test_explicit_date_is_returned():
    resolved, error = resolve_date(
        DATES,
        last_date=None,
        day_number=None,
        offset=None,
        date="2024-01-03",
    )

    assert resolved == "2024-01-03"
    assert error is None


def test_explicit_date_not_in_list_returns_error():
    resolved, error = resolve_date(
        DATES,
        last_date=None,
        day_number=None,
        offset=None,
        date="2024-02-01",
    )

    assert resolved is None
    assert error is not None