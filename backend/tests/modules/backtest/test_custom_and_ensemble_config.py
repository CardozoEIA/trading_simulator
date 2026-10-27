from datetime import date

import pytest
from fastapi import HTTPException

from app.modules.backtest import service
from app.modules.backtest.schema import BacktestConfiguration
from app.modules.custom_strategies import service as custom_service
from tests.fake_supabase import FakeSupabase

USER, OTHER = "user-1", "user-2"
MINE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
THEIRS = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase(
        historical_data=[{"asset": "SP500", "date": "2020-06-01"}],
        custom_strategies=[
            {"id": MINE, "user_id": USER, "name": "Quick SMA", "base_strategy": "SMA",
             "params": {"short_period": 3, "long_period": 8}},
            {"id": THEIRS, "user_id": OTHER, "name": "Not mine", "base_strategy": "RSI",
             "params": {"period": 14, "oversold": 30, "overbought": 70}},
        ],
    )
    monkeypatch.setattr(service, "supabase", fake)
    monkeypatch.setattr(custom_service, "supabase", fake)
    return fake


def config(**changes):
    values = dict(asset="SP500", start_date=date(2020, 1, 1), end_date=date(2020, 12, 31), initial_capital=10000,
                  strategies=["RSI"], custom_strategy_ids=[], ensemble_threshold=None)
    values.update(changes)
    return BacktestConfiguration(**values)


def error_of(call):
    with pytest.raises(HTTPException) as error:
        call()
    return error.value


def test_a_configuration_can_use_only_custom_strategies(db):
    configuration = config(strategies=[], custom_strategy_ids=[MINE])
    assert service.validate_configuration(configuration, USER) >= 1
    saved = service.save_configuration(configuration, USER, 1)
    assert saved["strategies"] == ["CUSTOM:Quick SMA"]
    stored = db.tables["backtest_configurations"][0]
    assert stored["custom_strategies"] == [
        {"id": MINE, "name": "Quick SMA", "base_strategy": "SMA", "params": {"short_period": 3, "long_period": 8}}]


def test_built_in_and_custom_strategies_can_be_combined_with_a_threshold(db):
    configuration = config(strategies=["RSI", "SMA"], custom_strategy_ids=[MINE], ensemble_threshold=0.2)
    service.validate_configuration(configuration, USER)
    saved = service.save_configuration(configuration, USER, 1)
    assert saved["strategies"] == ["RSI", "SMA", "CUSTOM:Quick SMA"]
    assert saved["ensemble_threshold"] == 0.2
    assert db.tables["backtest_configurations"][0]["ensemble_threshold"] == 0.2


def test_a_saved_configuration_keeps_a_snapshot_when_the_strategy_changes_later(db):
    configuration = config(strategies=[], custom_strategy_ids=[MINE])
    service.save_configuration(configuration, USER, 1)
    custom_service.update_custom_strategy(MINE, USER, "Quick SMA", "SMA", {"short_period": 10, "long_period": 50})
    assert db.tables["backtest_configurations"][0]["custom_strategies"][0]["params"] == {"short_period": 3, "long_period": 8}


def test_a_configuration_without_any_strategy_is_rejected(db):
    assert error_of(lambda: service.validate_configuration(config(strategies=[]), USER)).status_code == 400


def test_someone_elses_or_missing_custom_strategy_is_a_404(db):
    assert error_of(lambda: service.validate_configuration(config(custom_strategy_ids=[THEIRS]), USER)).status_code == 404
    assert error_of(lambda: service.validate_configuration(config(custom_strategy_ids=["nope"]), USER)).status_code == 404


def test_custom_strategies_need_a_known_student(db):
    assert error_of(lambda: service.validate_configuration(config(custom_strategy_ids=[MINE]))).status_code == 400


@pytest.mark.parametrize("threshold", [0, -0.1, 1.5])
def test_the_ensemble_threshold_must_be_between_zero_and_one(db, threshold):
    assert error_of(lambda: service.validate_configuration(config(ensemble_threshold=threshold), USER)).status_code == 400


def test_duplicates_and_too_many_strategies_are_rejected(db):
    assert error_of(lambda: service.validate_configuration(config(strategies=["RSI", "RSI"]), USER)).status_code == 400
    many = [MINE] * 3  # repeated custom ids count once
    assert service.validate_configuration(config(strategies=[], custom_strategy_ids=many), USER) >= 1


def test_a_copy_of_a_configuration_reuses_the_original_snapshots(db):
    snapshots = [{"id": MINE, "name": "Old name", "base_strategy": "RSI", "params": {"period": 9}}]
    saved = service.save_configuration(config(strategies=["SMA"], custom_strategy_ids=[MINE]), USER, 1, custom_snapshots=snapshots)
    assert saved["strategies"] == ["SMA", "CUSTOM:Old name"]


def test_the_strategy_list_shows_built_ins_then_the_students_own(db):
    items = service.get_available_strategies(USER)
    assert [i["code"] for i in items[:4]] == ["SMA", "RSI", "BOLLINGER", "MOMENTUM"]
    assert not any(i["custom"] for i in items[:4])
    assert items[4] == {"code": f"CUSTOM:{MINE}", "name": "Quick SMA", "custom": True,
                        "description": "Custom SMA strategy: short average 3, long average 8"}
    assert len(items) == 5  # nobody else's strategy appears
    assert len(service.get_available_strategies()) == 4


def test_the_strategy_list_survives_a_database_failure_reading_custom_ones(db):
    db.fail = True
    assert len(service.get_available_strategies(USER)) == 4
