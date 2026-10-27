from app.agents.whatif import graph as whatif_graph
from tests.agents.whatif.test_whatif import FakeBackend, what_if
from tests.agents.chat.test_conversation import offline  # noqa: F401 (fixture)

SNAPSHOT = {"id": "11111111-1111-4111-8111-111111111111", "name": "Quick SMA", "base_strategy": "SMA",
            "params": {"short_period": 3, "long_period": 8}}


def test_what_if_of_a_simulation_with_custom_strategies_keeps_their_snapshot(monkeypatch):
    backend = FakeBackend().install(monkeypatch)
    backend.original["strategies"] = ["RSI", "CUSTOM:Quick SMA"]
    backend.original["custom_strategies"] = [SNAPSHOT]
    backend.original["ensemble_threshold"] = 0.2
    received = {}

    def save_configuration(configuration, user_id, records, custom_snapshots=None):
        received.update(configuration=configuration, snapshots=custom_snapshots)
        return {"id": "cfg-new"}

    monkeypatch.setattr(whatif_graph, "save_configuration", save_configuration)
    what_if(backend)

    configuration = received["configuration"]
    assert [s.value for s in configuration.strategies] == ["RSI"]          # codes only; customs travel as snapshots
    assert configuration.custom_strategy_ids == [SNAPSHOT["id"]]
    assert configuration.ensemble_threshold == 0.2
    assert received["snapshots"] == [SNAPSHOT]                              # the copy runs the ORIGINAL parameters
    assert backend.runs == [("cfg-new", "user-1")]
