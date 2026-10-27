from datetime import date

import pytest
from fastapi import HTTPException

from app.agents.explain.tools import describe_regime
from app.modules.regime import service
from app.services.regime.classifier import MODEL_VERSION, Regime, RegimeLabel, build_regime_labels
from tests.fake_supabase import FakeSupabase
from tests.services.regime.test_classifier import NORMAL_HISTORY, make_candles


def label(day, regime=Regime.TRENDING):
    return RegimeLabel(
        date=day, regime=regime, volatility=0.15, trend_strength=0.4,
        checkpoint_date=date(2020, 1, 2), model_version=f"{MODEL_VERSION}@2020-01-02",
    )


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(service, "supabase", fake)
    return fake


def test_labels_are_saved_with_their_version_and_replaced_on_rerun(db):
    labels = [label(date(2021, 3, 1)), label(date(2021, 3, 2), Regime.RANGE_BOUND)]
    assert service.save_regime_labels("SP500", labels) == 2
    service.save_regime_labels("SP500", [label(date(2021, 3, 1), Regime.HIGH_VOLATILITY)])

    rows = db.tables["market_regimes"]
    assert len(rows) == 2
    first = next(r for r in rows if r["date"] == "2021-03-01")
    assert first["regime"] == "HIGH_VOLATILITY"
    assert first["algorithm_version"] == MODEL_VERSION
    assert first["checkpoint_date"] == "2020-01-02"
    assert first["model_version"] == f"{MODEL_VERSION}@2020-01-02"


def test_load_returns_only_the_requested_period_and_version(db):
    service.save_regime_labels("SP500", [label(date(2021, 3, d)) for d in range(1, 6)])
    db.tables["market_regimes"].append(
        {**db.tables["market_regimes"][0], "algorithm_version": "old-version", "regime": "RANGE_BOUND"}
    )
    loaded = service.load_regime_labels("SP500", date(2021, 3, 2), date(2021, 3, 4))
    assert sorted(loaded) == [date(2021, 3, 2), date(2021, 3, 3), date(2021, 3, 4)]
    assert all(item.regime == Regime.TRENDING for item in loaded.values())


def test_regime_on_or_before_uses_the_previous_trading_day(db):
    service.save_regime_labels("SP500", [label(date(2021, 3, 5), Regime.RANGE_BOUND)])
    assert service.regime_on_or_before("SP500", date(2021, 3, 7)).regime == Regime.RANGE_BOUND  # a Sunday
    assert service.regime_on_or_before("SP500", date(2021, 3, 1)) is None


def test_database_failure_is_a_503(db):
    db.fail = True
    with pytest.raises(HTTPException) as error:
        service.load_regime_labels("SP500", date(2021, 1, 1), date(2021, 2, 1))
    assert error.value.status_code == 503


def test_simulation_period_uses_stored_labels_when_they_exist(db):
    candles = make_candles([(10, 0.0, 0.01)], start=date(2021, 3, 1))
    service.save_regime_labels("SP500", [label(c.date, Regime.RANGE_BOUND) for c in candles])
    result = service.regimes_for_candles("SP500", candles)
    assert len(result) == 10
    assert {item.regime for item in result.values()} == {Regime.RANGE_BOUND}


def test_without_stored_labels_they_are_recomputed_from_the_history(db):
    history = make_candles(NORMAL_HISTORY + [(60, 0.0, 0.006)], seed=21)
    db.tables["historical_data"] = [
        {"asset": "SP500", "date": c.date.isoformat(), "open": c.close, "high": c.close,
         "low": c.close, "close": c.close, "volume": 1}
        for c in history
    ]
    simulation = history[-40:]
    result = service.regimes_for_candles("SP500", simulation)
    expected = {x.date: x for x in build_regime_labels(history) if x.date >= simulation[0].date}
    assert result == expected and len(result) == 40


def test_a_simulation_still_runs_when_regimes_cannot_be_computed(db):
    db.fail = True
    assert service.regimes_for_candles("SP500", make_candles([(5, 0.0, 0.01)])) == {}


def test_regime_text_for_the_agent():
    text = describe_regime({"regime": "HIGH_VOLATILITY", "regime_model_version": "wf-regime-v1@2020-01-02"})
    assert "high volatility" in text and "wf-regime-v1@2020-01-02" in text
    assert "No market regime" in describe_regime({"regime": None})
