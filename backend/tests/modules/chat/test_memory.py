import pytest

from app.modules.chat import history, memory


def vector(*values):
    return list(values)


@pytest.fixture
def stored(monkeypatch):
    """A conversation of 12 turns (24 messages). Turn 0 is about RSI, turn 1 about drawdown."""
    turns = [
        {"turn_id": "t-rsi", "embedding": vector(1, 0, 0)},
        {"turn_id": "t-drawdown", "embedding": vector(0, 1, 0)},
        {"turn_id": "t-stop", "embedding": vector(0, 0, 1)},
    ] + [{"turn_id": f"t-filler-{i}", "embedding": vector(0, 0, 1)} for i in range(7)] + [
        {"turn_id": "t-recent-1", "embedding": vector(1, 0, 0)},
        {"turn_id": "t-recent-2", "embedding": vector(1, 0, 0)},
    ]

    messages = {
        "t-rsi": [("user", "What is the RSI?"), ("assistant", "RSI measures momentum from 0 to 100.")],
        "t-drawdown": [("user", "What is max drawdown?"), ("assistant", "The biggest fall from a peak.")],
        "t-stop": [("user", "What is a stop-loss?"), ("assistant", "It sells a losing position.")],
    }

    monkeypatch.setattr(history, "count_messages", lambda user_id, simulation_id: 24)
    monkeypatch.setattr(history, "load_turn_embeddings", lambda user_id, simulation_id: turns)
    monkeypatch.setattr(
        history,
        "load_turns",
        lambda user_id, simulation_id, turn_ids: [
            {"turn_id": turn_id, "role": role, "content": content}
            for turn_id in turn_ids
            for role, content in messages.get(turn_id, [])
        ],
    )
    return turns


def test_cosine():
    assert memory.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert memory.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert memory.cosine([0, 0], [1, 1]) == 0.0


def test_short_histories_are_not_searched(monkeypatch):
    monkeypatch.setattr(history, "count_messages", lambda user_id, simulation_id: memory.HISTORY_THRESHOLD)

    def must_not_embed(text):
        raise AssertionError("A short conversation must not trigger an embedding search")

    monkeypatch.setattr(memory, "embed_text", must_not_embed)

    assert memory.build_memory_context("user-1", "sim-1", "What is the RSI?") is None


def test_long_histories_return_only_the_relevant_turns(monkeypatch, stored):
    monkeypatch.setattr(memory, "embed_text", lambda text: vector(0.9, 0.1, 0))  # close to the RSI turn

    context = memory.build_memory_context("user-1", "sim-1", "Remind me about the RSI")

    assert "RSI measures momentum" in context
    assert context.startswith("Earlier in this conversation")
    # Not the whole transcript: three turns at most.
    assert context.count("Student:") <= memory.TOP_K


def test_the_newest_turns_are_not_repeated(monkeypatch, stored):
    monkeypatch.setattr(memory, "embed_text", lambda text: vector(1, 0, 0))

    context = memory.build_memory_context("user-1", "sim-1", "RSI again")

    assert "t-recent" not in context  # they are already in the live conversation


def test_relevant_turns_come_back_in_chronological_order(monkeypatch, stored):
    monkeypatch.setattr(memory, "embed_text", lambda text: vector(1, 1, 0.01))  # RSI and drawdown close

    context = memory.build_memory_context("user-1", "sim-1", "RSI and drawdown")

    assert context.index("What is the RSI?") < context.index("What is max drawdown?")


def test_without_an_embedding_model_there_is_no_context(monkeypatch, stored):
    monkeypatch.setattr(memory, "embed_text", lambda text: None)

    assert memory.build_memory_context("user-1", "sim-1", "What is the RSI?") is None


def test_long_messages_are_clipped(monkeypatch, stored):
    monkeypatch.setattr(memory, "embed_text", lambda text: vector(1, 0, 0))
    monkeypatch.setattr(
        history,
        "load_turns",
        lambda *a, **k: [{"turn_id": "t-rsi", "role": "assistant", "content": "word " * 500}],
    )

    context = memory.build_memory_context("user-1", "sim-1", "RSI")

    assert len(context.splitlines()[1]) <= memory.MAX_CHARS_PER_MESSAGE + len("Assistant: ")


def test_remember_turn_stores_the_embedding(monkeypatch):
    saved = []
    monkeypatch.setattr(memory, "embed_text", lambda text: vector(0.5, 0.5))
    monkeypatch.setattr(history, "save_turn", lambda *args, **kwargs: saved.append((args, kwargs)))

    memory.remember_turn("user-1", "sim-1", "What is the RSI?", {"reply": "A momentum indicator."})

    assert saved[0][1]["embedding"] == [0.5, 0.5]


def test_remember_turn_still_saves_when_embedding_fails(monkeypatch):
    saved = []
    monkeypatch.setattr(memory, "embed_text", lambda text: None)
    monkeypatch.setattr(history, "save_turn", lambda *args, **kwargs: saved.append((args, kwargs)))

    memory.remember_turn("user-1", "sim-1", "What is the RSI?", {"reply": "A momentum indicator."})

    assert saved and saved[0][1]["embedding"] is None
