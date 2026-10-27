# app/agents/explain/verify.py
"""US-31: self-verification (reflection) for explanations, plus the traceability record.

Before an explanation is shown, every sentence is checked against what the tools returned during the run:
a date or number that no tool result contains means the sentence is not backed by data, so it is removed and
the student is told. The model is never asked to grade itself: the check is deterministic.
"""
import re
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.insights.verify import _numbers, makes_promises, unverified_values

LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(*])")
MARKDOWN_RE = re.compile(r"[*_`#]")

NOTHING_VERIFIED = (
    "I could not back this explanation with the simulation data, so I am not showing it. "
    "This is what the data says:"
)
NO_DATA = "The tools returned no data for this request."


@dataclass
class VerificationResult:
    text: str
    verified: bool                       # True when nothing had to be removed
    removed: list[dict] = field(default_factory=list)   # [{"statement", "problems"}]
    tools_called: int = 0

    def as_dict(self) -> dict:
        return {
            "verified": self.verified,
            "tools_called": self.tools_called,
            "removed": self.removed,
        }


def extract_trace(messages: list) -> list[dict]:
    """The tool calls of the LAST run (after the last human message) with the value each one returned."""
    start = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1) + 1
    calls, trace = {}, []
    for message in messages[start:]:
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                entry = {"tool": call["name"], "arguments": call.get("args") or {}, "result": None}
                calls[call.get("id")] = entry
                trace.append(entry)
        elif isinstance(message, ToolMessage):
            entry = calls.get(message.tool_call_id)
            if entry is not None:
                entry["result"] = message.content if isinstance(message.content, str) else str(message.content)
    return trace


def _facts(trace: list[dict], request_text: str, reference_facts: str) -> str:
    """Everything an answer may rely on: tool results, the student's own request and the strategy definition."""
    parts = [entry["result"] for entry in trace if entry.get("result")]
    parts.append(request_text or "")
    parts.append(reference_facts or "")
    text = "\n".join(parts)
    # A ratio such as momentum 0.0523 is legitimately written as 5.23%.
    derived = [f"{value * 100:.4f}" for value in _numbers(text) if 0 < abs(value) < 1]
    return text + "\nDerived percentages: " + " ".join(derived)


def split_statements(answer: str) -> list[str]:
    statements = []
    for line in answer.split("\n"):
        if not line.strip():
            continue
        marker = LIST_MARKER_RE.match(line)
        prefix = marker.group(0) if marker else ""  # "1. " must not be cut off as a sentence of its own
        parts = [part for part in SENTENCE_SPLIT_RE.split(line[len(prefix):]) if part.strip()]
        if parts:
            parts[0] = prefix + parts[0]
        statements.extend(parts)
    return statements


def _plain(statement: str) -> str:
    return MARKDOWN_RE.sub("", LIST_MARKER_RE.sub("", statement)).strip()


def _fallback(trace: list[dict]) -> str:
    lines = [f"- {entry['result']}" for entry in trace if entry.get("result")]
    return "\n".join([NOTHING_VERIFIED, *lines]) if lines else NO_DATA


def verify_answer(answer: str, trace: list[dict], request_text: str = "", reference_facts: str = "") -> VerificationResult:
    """Removes the sentences whose dates or numbers no tool returned (or that promise future results)."""
    facts = _facts(trace, request_text, reference_facts)
    kept, removed = [], []

    for statement in split_statements(answer or ""):
        text = _plain(statement)
        problems = unverified_values(text, facts)
        if makes_promises(text):
            problems.append("promises a future result")
        if problems:
            removed.append({"statement": statement.strip(), "problems": problems})
        else:
            kept.append(statement)

    if not kept:
        return VerificationResult(_fallback(trace), verified=not removed and not (answer or "").strip(),
                                  removed=removed, tools_called=len(trace))
    if removed:
        note = (f"Note: {len(removed)} statement{'s' if len(removed) > 1 else ''} removed because "
                "the values in them were not found in the simulation data.")
        return VerificationResult("\n".join(kept) + "\n\n" + note, verified=False, removed=removed, tools_called=len(trace))
    return VerificationResult(answer.strip(), verified=True, removed=[], tools_called=len(trace))
