"""Routing accuracy against the REAL local model.

Skipped by default because it needs Ollama running. Run it with:

    set RUN_OLLAMA_TESTS=1      (Windows PowerShell: $env:RUN_OLLAMA_TESTS=1)
    pytest app/services/agent/conversation/test_routing_accuracy.py -v -s
"""
import os

import pytest
from langchain_ollama import ChatOllama

from app.services.agent.conversation.router import classify_question

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="Needs Ollama running. Set RUN_OLLAMA_TESTS=1 to run it.",
)

MIN_ACCURACY = 0.85

# (question, last discussed date, expected route)
CASES = [
    ("Why did it sell on day 16?", None, "explain_agent"),
    ("Why did the strategy buy on day 3?", None, "explain_agent"),
    ("Explain the decision on 2023-10-19", None, "explain_agent"),
    ("And the next day?", "2023-10-19", "explain_agent"),
    ("Why did it do that?", "2023-10-19", "explain_agent"),
    ("What happened the day before?", "2023-10-19", "explain_agent"),
    ("Give me an overview of this simulation", None, "insights_agent"),
    ("How did my strategy perform overall?", None, "insights_agent"),
    ("What were the main strengths and weaknesses of this run?", None, "insights_agent"),
    ("Did the strategy beat buy & hold?", None, "answer"),
    ("How do my results compare with simply holding the asset?", None, "answer"),
    ("What is the RSI?", None, "conceptual"),
    ("What does max drawdown mean?", None, "conceptual"),
    ("How does a stop-loss work?", None, "conceptual"),
    ("Explain what the Sharpe ratio is", None, "conceptual"),
    ("What is buy & hold?", None, "conceptual"),
    ("Try a 3% stop-loss", None, "propose_change"),
    ("What if I set the max drawdown to 15?", None, "propose_change"),
    ("Change my max position size to 40%", None, "propose_change"),
    ("Tell me more", None, "clarify"),
    ("Why did it sell?", None, "clarify"),
    ("asdf", None, "clarify"),
]


def test_routing_accuracy():
    llm = ChatOllama(model="qwen2.5:7b", temperature=0, format="json")

    misses = []

    for question, last_date, expected in CASES:
        actual = classify_question(llm, question, last_date)["next_step"]
        if actual != expected:
            misses.append((question, expected, actual))

    accuracy = 1 - len(misses) / len(CASES)

    print(f"\nRouting accuracy: {accuracy:.0%} ({len(CASES) - len(misses)}/{len(CASES)})")
    for question, expected, actual in misses:
        print(f"  MISS: {question!r} expected={expected} got={actual}")

    assert accuracy >= MIN_ACCURACY