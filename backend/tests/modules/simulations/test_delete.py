# tests/modules/simulations/test_delete.py
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.modules.simulations import routes, service

SIMULATION = {"id": "sim-1", "configuration_id": "cfg-1", "status": "FINISHED"}


class Query:
    def __init__(self, db, table):
        self.db, self.table, self.action, self.filters = db, table, "select", []

    def delete(self):
        self.action = "delete"
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, *args):
        return self

    def execute(self):
        if self.db.fail_on == self.table:
            raise RuntimeError("connection reset")
        if self.action == "delete":
            self.db.deleted.append((self.table, tuple(self.filters)))
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=self.db.other_simulations_on_config)


class FakeSupabase:
    def __init__(self, other_simulations_on_config=(), fail_on=None):
        self.other_simulations_on_config = list(other_simulations_on_config)
        self.fail_on, self.deleted = fail_on, []

    def table(self, name):
        return Query(self, name)

    def tables(self):
        return [table for table, _ in self.deleted]


@pytest.fixture
def owned(monkeypatch):
    monkeypatch.setattr(service, "get_simulation_status", lambda sim_id, user_id: dict(SIMULATION))


def install(monkeypatch, **kwargs):
    db = FakeSupabase(**kwargs)
    monkeypatch.setattr(service, "supabase", db)
    return db


def test_deletes_the_recorded_data_then_the_simulation_and_its_unused_configuration(owned, monkeypatch):
    db = install(monkeypatch)
    service.delete_simulation("sim-1", "user-1")

    assert db.tables() == [*service.SIMULATION_CHILD_TABLES, "simulations",
                           "risk_configurations", "backtest_configurations"]
    assert ("simulations", (("id", "sim-1"), ("user_id", "user-1"))) in db.deleted
    assert ("backtest_configurations", (("id", "cfg-1"), ("user_id", "user-1"))) in db.deleted
    for table in service.SIMULATION_CHILD_TABLES:
        assert (table, (("simulation_id", "sim-1"),)) in db.deleted


def test_configuration_used_by_another_simulation_is_kept(owned, monkeypatch):
    db = install(monkeypatch, other_simulations_on_config=[{"id": "sim-2"}])
    service.delete_simulation("sim-1", "user-1")
    assert "backtest_configurations" not in db.tables()
    assert "risk_configurations" not in db.tables()


def test_foreign_simulation_is_404_and_nothing_is_deleted(monkeypatch):
    def not_owned(sim_id, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    monkeypatch.setattr(service, "get_simulation_status", not_owned)
    db = install(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.delete_simulation("sim-1", "someone-else")
    assert exc.value.status_code == 404
    assert db.deleted == []


def test_running_simulation_is_409_and_nothing_is_deleted(monkeypatch):
    monkeypatch.setattr(service, "get_simulation_status", lambda sim_id, user_id: {**SIMULATION, "status": "RUNNING"})
    db = install(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.delete_simulation("sim-1", "user-1")
    assert exc.value.status_code == 409
    assert db.deleted == []


def test_database_error_is_503_and_the_simulation_row_is_not_deleted(owned, monkeypatch):
    db = install(monkeypatch, fail_on="simulation_signals")
    with pytest.raises(HTTPException) as exc:
        service.delete_simulation("sim-1", "user-1")
    assert exc.value.status_code == 503
    assert "simulations" not in db.tables()  # still listed, so deleting again finishes the job


# --- endpoint ---

@pytest.fixture
def client(monkeypatch):
    forgotten = []
    monkeypatch.setattr(routes, "forget_conversation", lambda sim_id, user_id: forgotten.append((sim_id, user_id)))
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    test_client = TestClient(app)
    test_client.forgotten = forgotten
    return test_client


def test_endpoint_returns_204_and_forgets_the_conversation(client, monkeypatch):
    deleted = []
    monkeypatch.setattr(routes, "delete_simulation", lambda sim_id, user_id: deleted.append((sim_id, user_id)))
    response = client.delete("/simulations/sim-1")
    assert response.status_code == 204
    assert deleted == [("sim-1", "user-1")]
    assert client.forgotten == [("sim-1", "user-1")]


def test_endpoint_keeps_the_conversation_when_the_delete_fails(client, monkeypatch):
    def not_owned(sim_id, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    monkeypatch.setattr(routes, "delete_simulation", not_owned)
    assert client.delete("/simulations/foreign").status_code == 404
    assert client.forgotten == []
