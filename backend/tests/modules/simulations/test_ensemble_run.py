"""End to end: start_simulation with an in-memory database (US-21, US-23, US-24)."""
import pytest

from app.modules.decisions import service as decisions_service
from app.modules.portfolio import service as portfolio_service
from app.modules.signals import service as signals_service
from app.modules.simulations import service
from app.services.historical_data.schema import ProcessedHistoricalData
from app.services.regime.classifier import build_regime_labels
from tests.fake_supabase import FakeSupabase
from tests.services.regime.test_classifier import make_candles

USER, CONFIG = "user-1", "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


@pytest.fixture(scope="module")
def candles():
    return make_candles([(300, 0.0006, 0.009), (120, -0.002, 0.025), (200, 0.0008, 0.008)], seed=12)


def install(monkeypatch, candles, strategies, custom=None, threshold=None, with_regimes=True):
    config = {
        "id": CONFIG, "user_id": USER, "asset": "SP500", "initial_capital": 10000,
        "start_date": candles[0].date.isoformat(), "end_date": candles[-1].date.isoformat(),
        "strategies": strategies, "custom_strategies": custom or [], "ensemble_threshold": threshold,
    }
    db = FakeSupabase(
        backtest_configurations=[config],
        risk_configurations=[{"configuration_id": CONFIG, "user_id": USER,
                              "stop_loss_percentage": 10, "max_position_size": 50, "max_drawdown": 60}],
    )
    for module in (service, portfolio_service, decisions_service, signals_service):
        monkeypatch.setattr(module, "supabase", db)
    monkeypatch.setattr(service, "process_historical_data", lambda **_: ProcessedHistoricalData(
        asset="SP500", candles=candles, gaps=[], total_records=len(candles)))
    labels = {x.date: x for x in build_regime_labels(candles)} if with_regimes else {}
    monkeypatch.setattr(service, "regimes_for_candles", lambda asset, c: labels)
    return db


def actions(db):
    return [(r["date"], r["action"]) for r in db.tables["simulation_decisions"]]


def test_two_strategies_are_blended_and_every_decision_keeps_its_breakdown(monkeypatch, candles):
    db = install(monkeypatch, candles, ["SMA", "RSI"])
    result = service.start_simulation(CONFIG, USER)
    assert result["status"] in ("FINISHED", "STOPPED_BY_RISK")

    rows = db.tables["simulation_decisions"]
    assert rows and all("breakdown" in r for r in rows)
    with_regime = [r for r in rows if r["breakdown"]["regime"] != "UNKNOWN"]
    assert with_regime, "late days must carry a regime"
    sample = with_regime[-1]["breakdown"]
    assert {c["strategy"] for c in sample["components"]} == {"SMA", "RSI"}
    assert sum(c["weight"] for c in sample["components"]) == pytest.approx(1.0)
    assert sample["threshold"] == 0.1


def test_regime_is_stored_next_to_the_signals(monkeypatch, candles):
    db = install(monkeypatch, candles, ["SMA"])
    service.start_simulation(CONFIG, USER)
    signals = db.tables["simulation_signals"]
    labelled = [s for s in signals if s.get("regime")]
    assert labelled and {s["regime"] for s in labelled} <= {"HIGH_VOLATILITY", "TRENDING", "RANGE_BOUND"}
    assert all(s["regime_model_version"].startswith("wf-regime-v1@") for s in labelled)
    assert len(labelled) < len(signals)  # the first days have no label: nothing to train on yet


def test_one_strategy_is_unchanged_by_the_ensemble_and_the_regime(monkeypatch, candles):
    with_labels = install(monkeypatch, candles, ["RSI"])
    service.start_simulation(CONFIG, USER)
    with_regimes = actions(with_labels)
    assert all("breakdown" not in r for r in with_labels.tables["simulation_decisions"])

    without = install(monkeypatch, candles, ["RSI"], with_regimes=False)
    service.start_simulation(CONFIG, USER)
    assert actions(without) == with_regimes  # regimes are context only: decisions do not depend on them


def test_the_regime_changes_the_blend_but_not_a_single_strategy(monkeypatch, candles):
    labelled = install(monkeypatch, candles, ["SMA", "RSI"])
    service.start_simulation(CONFIG, USER)
    unlabelled = install(monkeypatch, candles, ["SMA", "RSI"], with_regimes=False)
    service.start_simulation(CONFIG, USER)
    assert actions(labelled) != actions(unlabelled)


def test_a_custom_strategy_runs_from_its_saved_snapshot(monkeypatch, candles):
    snapshot = {"id": "11111111-1111-4111-8111-111111111111", "name": "Quick SMA", "base_strategy": "SMA",
                "params": {"short_period": 3, "long_period": 8}}
    db = install(monkeypatch, candles, ["CUSTOM:Quick SMA"], custom=[snapshot])
    service.start_simulation(CONFIG, USER)
    custom_run = actions(db)

    from app.services.strategy.engine import run_strategy
    from app.services.strategy.strategies import sma
    expected = run_strategy(candles, [sma.build_evaluate(3, 8)])
    assert [a for _, a in custom_run] == [d.action.value for d in expected[: len(custom_run)]]
    assert any(a != "HOLD" for _, a in custom_run)


def test_built_in_and_custom_strategies_are_combined(monkeypatch, candles):
    snapshot = {"id": "22222222-2222-4222-8222-222222222222", "name": "Patient RSI", "base_strategy": "RSI",
                "params": {"period": 21, "oversold": 25, "overbought": 75}}
    db = install(monkeypatch, candles, ["SMA", "CUSTOM:Patient RSI"], custom=[snapshot], threshold=0.15)
    service.start_simulation(CONFIG, USER)
    breakdown = db.tables["simulation_decisions"][-1]["breakdown"]
    assert breakdown["threshold"] == 0.15
    assert [(c["strategy"], c["based_on"]) for c in breakdown["components"]] == [
        ("SMA", "SMA"), ("CUSTOM:Patient RSI", "RSI")]


def test_the_same_configuration_gives_the_same_simulation(monkeypatch, candles):
    first = install(monkeypatch, candles, ["SMA", "RSI", "MOMENTUM"])
    service.start_simulation(CONFIG, USER)
    second = install(monkeypatch, candles, ["SMA", "RSI", "MOMENTUM"])
    service.start_simulation(CONFIG, USER)
    assert first.tables["simulation_decisions"] == second.tables["simulation_decisions"]
    assert first.tables["simulation_trades"] == second.tables["simulation_trades"]
