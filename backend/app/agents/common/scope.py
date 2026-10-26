"""Keeps the agents on topic: trading, the student's simulations and the platform.

Deterministic checks that run before any model call, and the fixed replies used when a
question is out of scope. Fixed text (instead of model text) means an off-topic or
manipulative question never gets an answer that engages with it.
"""
import re

# Attempts to override the agent's instructions (English and Spanish).
INJECTION_RE = re.compile(
    r"ignore (all |any |the |your )*(previous |above |prior |earlier )?(instructions|rules|prompts?|directions)|"
    r"disregard .{0,30}(instructions|rules)|forget (all |your |the )?(previous |prior )?(instructions|rules)|"
    r"system prompt|reveal your (prompt|instructions)|new instructions|"
    r"you are (now|no longer)|pretend (to be|you are)|act as (a|an) |jailbreak|developer mode|"
    r"olvida (tus|las) instrucciones|ignora (tus|las|todas las) (instrucciones|reglas)",
    re.IGNORECASE,
)

OFF_TOPIC_REPLY = (
    "I can only help with trading and your simulations. For example, ask why the strategy "
    "bought or sold on a day, for an overview of this simulation, whether it beat buy & hold, "
    "what a trading term like RSI or drawdown means, to try a different risk limit, or to "
    "compare it with another of your simulations."
)


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION_RE.search(text or ""))
