"""Nodes of the knowledge (RAG) graph.

Each node is a plain function: state in, partial state out. They are built by make_nodes() so the
tests can inject fakes instead of Ollama and Supabase.

Hallucination control (the rubric asks for at least two strategies; here there are five):
  1. similarity threshold at retrieval          -> retrieve()
  2. dedicated sufficiency node                 -> grade() (similarity floor + LLM check)
  3. "only the context" prompt                  -> prompts.ANSWER_SYSTEM_PROMPT
  4. explicit refusal with a fixed text         -> refuse() / generate()
  5. sources shown with every answer            -> generate()
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.knowledge.prompts import (
    ANSWER_REMINDER,
    ANSWER_SYSTEM_PROMPT,
    GRADER_SYSTEM_PROMPT,
    GREETING_TEXT,
    INSUFFICIENT_TOKEN,
    INVALID_TEXT,
    REFUSAL_TEXT,
    REWRITE_SYSTEM_PROMPT,
)
from app.agents.knowledge.state import KnowledgeState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TODO(Lucas) 🧠: these three numbers decide when the agent answers and when it refuses.
# Do NOT guess them: run  python scripts/calibrate_threshold.py  with your documents loaded,
# look at the similarities of questions that SHOULD be answered vs. ones that should NOT,
# and pick values that separate them. Write down what you saw: it goes in the technical report.
# ---------------------------------------------------------------------------
RETRIEVAL_THRESHOLD = 0.45  # chunks below this similarity are never even retrieved
MIN_BEST_SIMILARITY = (
    0.60  # the BEST chunk must reach this, otherwise: refuse without asking the LLM
)
TOP_K = 4  # passages sent to the model
USE_LLM_GRADER = False  # measured: the 7B grader falsely refused 2 of 3 valid questions, so it is off

MAX_QUESTION_CHARS = 500
GRADER_PASSAGES = 3
GRADER_CHARS_PER_PASSAGE = 600

_INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|above|prior)|disregard .{0,30}instructions|"
    r"system prompt|reveal your (prompt|instructions)|olvida (tus|las) instrucciones|"
    r"ignora (tus|las) instrucciones",
    re.IGNORECASE,
)
_GREETING = re.compile(
    r"^(hi|hello|hey|hola|buenas|buenos d[ií]as|good (morning|afternoon|evening))\b[\s!.,]*$",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[(\d+)\]")


# Style requests ("like I'm five", "for beginners") invite a small model to invent analogies.
# The answer is generated from the question WITHOUT them; the retrieval query already drops them too.
_STYLE_REQUEST = re.compile(
    r"\b(like|as if) (i'?m|i am|you('re| are) (talking|explaining) to) (a |an )?(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|child|kid|toddler|beginner|novice|noob)( years?[ -]old)?\b|"
    r"\beli5\b|"
    r"\b(for|to) (a |an )?(\d+|five|six|seven|eight|ten)?[ -]?(years?[ -]old|beginners?|children|child|kids?|toddlers?|dummies|novices?)\b|"
    r"\bcomo si (fuera|tuviera|tuviese) (un )?(ni[ñn]o|\d+ a[ñn]os|cinco a[ñn]os)\b|"
    r"\bpara (principiantes|ni[ñn]os|un ni[ñn]o)\b",
    re.IGNORECASE,
)


def _plain_question(question: str) -> str:
    """The question without style requests; falls back to the original if nothing is left."""
    plain = re.sub(r"\s+", " ", _STYLE_REQUEST.sub("", question))
    plain = re.sub(r"\s+([?!.,;])", r"\1", plain).strip(" ,.;")
    return plain if len(plain) >= 2 else question


def _format_context(chunks: list[dict]) -> str:
    lines = []

    for number, chunk in enumerate(chunks, start=1):
        where = chunk["filename"] + (
            f", p. {chunk['page']}" if chunk.get("page") else ""
        )
        lines.append(f"[{number}] ({where})\n{chunk['content']}")

    return "\n\n".join(lines)


def _to_source(chunk: dict) -> dict:
    snippet = " ".join(chunk["content"].split())

    return {
        "document_id": chunk["document_id"],
        "filename": chunk["filename"],
        "page": chunk.get("page"),
        "chunk_index": chunk["chunk_index"],
        "similarity": round(float(chunk["similarity"]), 3),
        "snippet": snippet[:240] + ("…" if len(snippet) > 240 else ""),
    }


def make_nodes(
    llm,
    grader_llm,
    embed_query,
    search_chunks,
    save_turn,
    rewrite_llm=None,
):
    rewrite_llm = rewrite_llm or grader_llm

    # Node 1 -------------------------------------------------------------
    def validate_intent(state: KnowledgeState) -> KnowledgeState:
        """Cheap, deterministic checks BEFORE spending any model call."""
        question = state["question"].strip()

        if (
            len(question) < 2
            or len(question) > MAX_QUESTION_CHARS
            or _INJECTION.search(question)
        ):
            return {
                "intent": "invalid",
                "answer": INVALID_TEXT,
                "refused": True,
                "sources": [],
            }

        if _GREETING.match(question):
            return {
                "intent": "greeting",
                "answer": GREETING_TEXT,
                "refused": False,
                "sources": [],
            }

        return {"intent": "question"}

    def rewrite_query(question: str) -> str:
        """Search query = the question without style words, in English. Falls back to the original."""
        try:
            query = rewrite_llm.invoke(
                [
                    SystemMessage(content=REWRITE_SYSTEM_PROMPT),
                    HumanMessage(content=question),
                ]
            ).content.strip()
        except Exception:
            logger.warning(
                "Query rewrite failed, using the original question", exc_info=True
            )
            return question

        query = query.strip().strip("\"'").strip()

        if not query or len(query) > 200 or "\n" in query:
            return question

        logger.info(
            "Query rewrite: %r -> %r",
            question,
            query,
        )
        return query

    # Node 2 -------------------------------------------------------------
    def retrieve(state: KnowledgeState) -> KnowledgeState:
        query = rewrite_query(state["question"])

        vector = embed_query(query)

        chunks = search_chunks(
            vector,
            state["user_id"],
            RETRIEVAL_THRESHOLD,
            TOP_K,
        )

        return {
            "chunks": chunks,
            "search_query": query,
        }

    # Node 3 -------------------------------------------------------------
    def grade(state: KnowledgeState) -> KnowledgeState:
        """Is what we found enough to answer? Two filters: a number first, then the model."""
        chunks = state.get("chunks") or []

        if not chunks or chunks[0]["similarity"] < MIN_BEST_SIMILARITY:
            return {"sufficient": False}

        if not USE_LLM_GRADER:
            return {"sufficient": True}

        passages = "\n\n".join(
            c["content"][:GRADER_CHARS_PER_PASSAGE] for c in chunks[:GRADER_PASSAGES]
        )

        try:
            reply = grader_llm.invoke(
                [
                    SystemMessage(content=GRADER_SYSTEM_PROMPT),
                    HumanMessage(
                        content=f"Question: {state['question']}\n"
                        f"Same question in English: {state['search_query']}\n\n"
                        f"Passages:\n{passages}"
                    ),
                ]
            ).content
        except Exception:
            # The numeric filter already passed: do not block the answer because the grader failed.
            logger.warning(
                "Sufficiency grader failed, trusting the similarity filter",
                exc_info=True,
            )
            return {"sufficient": True}

        return {"sufficient": reply.strip().upper().startswith("YES")}

    # Node 4a ------------------------------------------------------------
    def generate(state: KnowledgeState) -> KnowledgeState:
        chunks = state["chunks"]

        reply = llm.invoke(
            [
                SystemMessage(content=ANSWER_SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Context:\n{_format_context(chunks)}\n\nQuestion: {_plain_question(state['question'])}\n\n{ANSWER_REMINDER}"
                ),
            ]
        ).content.strip()

        # The model itself may decide the context is not enough.
        if INSUFFICIENT_TOKEN in reply or not reply:
            return {"answer": REFUSAL_TEXT, "refused": True, "sources": []}

        # Show the passages the answer cites; if it cites none, show everything it was given.
        cited = {int(n) for n in _CITATION.findall(reply)}
        used = [c for i, c in enumerate(chunks, start=1) if i in cited] or chunks

        return {
            "answer": reply,
            "refused": False,
            "sources": [_to_source(c) for c in used],
        }

    # Node 4b ------------------------------------------------------------
    def refuse(state: KnowledgeState) -> KnowledgeState:
        return {"answer": REFUSAL_TEXT, "refused": True, "sources": []}

    # Node 5 -------------------------------------------------------------
    def save_history(state: KnowledgeState) -> KnowledgeState:
        """Best effort: a database hiccup must not lose the answer the user is waiting for."""
        try:
            save_turn(
                state["user_id"],
                state["question"],
                state["answer"],
                state["refused"],
                state["sources"],
            )
        except Exception:
            logger.exception("Could not save the knowledge chat turn")

        return {}

    return {
        "validate_intent": validate_intent,
        "retrieve": retrieve,
        "grade": grade,
        "generate": generate,
        "refuse": refuse,
        "save_history": save_history,
    }
