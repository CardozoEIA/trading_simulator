import pytest
from fastapi import HTTPException

from app.modules.custom_strategies import service
from tests.fake_supabase import FakeSupabase

USER, OTHER = "user-1", "user-2"
ID_1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ID_2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(service, "supabase", fake)
    return fake


def error_of(call):
    with pytest.raises(HTTPException) as error:
        call()
    return error.value


def test_a_valid_strategy_is_saved_with_normalised_values(db):
    saved = service.create_custom_strategy(USER, "  Fast   SMA ", "SMA", {"short_period": 3, "long_period": 12})
    assert saved["name"] == "Fast SMA" and saved["user_id"] == USER
    assert saved["params"] == {"short_period": 3, "long_period": 12}


def test_missing_parameters_are_filled_with_defaults(db):
    saved = service.create_custom_strategy(USER, "Plain RSI", "RSI", {"period": 9})
    assert saved["params"] == {"period": 9, "oversold": 30, "overbought": 70}


def test_an_invalid_strategy_is_not_saved_and_lists_every_problem(db):
    error = error_of(lambda: service.create_custom_strategy(USER, "x", "SMA", {"short_period": 30, "long_period": 10}))
    assert error.status_code == 422
    assert len(error.detail) == 2  # the name is too short and the averages are inverted
    assert db.tables.get("custom_strategies", []) == []


def test_validation_without_saving(db):
    result = service.validate_strategy("Check me", "BOLLINGER", {"num_std": 3})
    assert result == {"name": "Check me", "base_strategy": "BOLLINGER", "params": {"period": 20, "num_std": 3.0}}
    assert db.tables.get("custom_strategies", []) == []
    assert error_of(lambda: service.validate_strategy("Check me", "BOLLINGER", {"num_std": 9})).status_code == 422


def test_names_are_unique_per_student_but_not_across_students(db):
    service.create_custom_strategy(USER, "Mine", "RSI", {})
    assert error_of(lambda: service.create_custom_strategy(USER, "Mine", "SMA", {})).status_code == 409
    assert service.create_custom_strategy(OTHER, "Mine", "RSI", {})["user_id"] == OTHER


def test_the_number_of_strategies_is_limited(db, monkeypatch):
    monkeypatch.setattr(service.custom, "MAX_CUSTOM_STRATEGIES", 2)
    service.create_custom_strategy(USER, "One", "RSI", {})
    service.create_custom_strategy(USER, "Two", "RSI", {})
    assert error_of(lambda: service.create_custom_strategy(USER, "Three", "RSI", {})).status_code == 409


def test_modify_before_saving_keeps_the_same_id_and_checks_the_new_values(db):
    service.create_custom_strategy(USER, "Tunable", "RSI", {})
    db.tables["custom_strategies"][0]["id"] = ID_1
    updated = service.update_custom_strategy(ID_1, USER, "Tunable v2", "RSI", {"oversold": 25, "overbought": 75})
    assert updated["id"] == ID_1 and updated["name"] == "Tunable v2"
    assert service.get_custom_strategy(ID_1, USER)["params"]["oversold"] == 25
    assert error_of(lambda: service.update_custom_strategy(ID_1, USER, "Tunable v2", "RSI", {"oversold": 80})).status_code == 422
    assert service.get_custom_strategy(ID_1, USER)["params"]["oversold"] == 25  # the failed edit changed nothing


def test_renaming_to_a_name_already_used_is_a_conflict(db):
    service.create_custom_strategy(USER, "First", "RSI", {})
    service.create_custom_strategy(USER, "Second", "RSI", {})
    db.tables["custom_strategies"][0]["id"], db.tables["custom_strategies"][1]["id"] = ID_1, ID_2
    assert error_of(lambda: service.update_custom_strategy(ID_2, USER, "First", "RSI", {})).status_code == 409
    assert service.update_custom_strategy(ID_2, USER, "Second", "RSI", {"period": 7})["params"]["period"] == 7  # same name is fine


def test_nobody_reads_edits_or_deletes_someone_elses_strategy(db):
    service.create_custom_strategy(USER, "Private", "RSI", {})
    db.tables["custom_strategies"][0]["id"] = ID_1
    assert error_of(lambda: service.get_custom_strategy(ID_1, OTHER)).status_code == 404
    assert error_of(lambda: service.update_custom_strategy(ID_1, OTHER, "Taken", "RSI", {})).status_code == 404
    assert error_of(lambda: service.delete_custom_strategy(ID_1, OTHER)).status_code == 404
    assert service.list_custom_strategies(OTHER) == []
    assert len(db.tables["custom_strategies"]) == 1


def test_delete_and_malformed_ids(db):
    service.create_custom_strategy(USER, "Temp", "RSI", {})
    db.tables["custom_strategies"][0]["id"] = ID_1
    service.delete_custom_strategy(ID_1, USER)
    assert service.list_custom_strategies(USER) == []
    assert error_of(lambda: service.get_custom_strategy("not-a-uuid", USER)).status_code == 404


def test_resolving_for_a_configuration_returns_snapshots_in_order(db):
    service.create_custom_strategy(USER, "Alpha", "RSI", {})
    service.create_custom_strategy(USER, "Beta", "SMA", {})
    db.tables["custom_strategies"][0]["id"], db.tables["custom_strategies"][1]["id"] = ID_1, ID_2
    snapshots = service.resolve_for_configuration([ID_2, ID_1, ID_2], USER)
    assert [s["name"] for s in snapshots] == ["Beta", "Alpha"]
    assert set(snapshots[0]) == {"id", "name", "base_strategy", "params"}
    assert error_of(lambda: service.resolve_for_configuration([ID_1], OTHER)).status_code == 404


def test_database_failure_is_a_503(db):
    db.fail = True
    assert error_of(lambda: service.list_custom_strategies(USER)).status_code == 503
