"""Export every agent graph as a Mermaid diagram (docs/agents/graphs/<name>.mmd).

Run from backend/:

    python -m scripts.export_agent_graphs

The graphs are only BUILT, never run: models are replaced by a fake object, the
Supabase settings by dummy values, and any attempt to open a network connection
fails, so the export works offline and never reaches Ollama or Supabase.
"""
import os
import socket
from pathlib import Path
from unittest import mock

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "agents" / "graphs"

# Dummy settings: app.core.supabase refuses to import without them. load_dotenv() does not
# override variables that are already set, so the real keys in backend/.env are never used.
for name in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SECRET_KEY"):
    os.environ[name] = "http://localhost.invalid" if name == "SUPABASE_URL" else "dummy"


def _no_network(*args, **kwargs):
    raise RuntimeError("export_agent_graphs must not open network connections")


class FakeModel:
    """Stands in for ChatOllama: graphs only need invoke() and bind_tools() to be built."""

    def __init__(self, *args, **kwargs):
        pass

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, *args, **kwargs):
        raise RuntimeError("the export only builds the graphs, it never runs them")


def _graphs() -> dict:
    """name -> compiled graph, built with fakes. Imports happen here, after the env is set."""
    from app.agents.chat.graph import build_conversation_graph
    from app.agents.compare.graph import build_compare_graph
    from app.agents.explain.graph import build_agent_graph
    from app.agents.insights.graph import build_insights_graph
    from app.agents.knowledge.graph import build_knowledge_graph
    from app.agents.report.graph import build_report_graph
    from app.agents.setup.graph import build_setup_graph
    from app.agents.whatif.graph import build_what_if_graph

    fake = FakeModel()
    unused = lambda *args, **kwargs: None  # noqa: E731  (dependencies only called when the graph runs)

    # explain and chat create ChatOllama themselves instead of taking llm=
    with mock.patch("app.agents.explain.graph.ChatOllama", FakeModel), \
         mock.patch("app.agents.chat.graph.ChatOllama", FakeModel):
        return {
            "explain": build_agent_graph("simulation-id", "user-id"),
            "chat": build_conversation_graph("simulation-id", "user-id", llm=fake, chat_llm=fake),
            "insights": build_insights_graph(llm=fake),
            "compare": build_compare_graph(llm=fake),
            "report": build_report_graph(llm=fake),
            "setup": build_setup_graph(llm=fake),
            "whatif": build_what_if_graph(llm=fake, runner=unused),
            "knowledge": build_knowledge_graph(
                llm=fake, grader_llm=fake, rewrite_llm=fake,
                embed_query=unused, search_chunks=unused, save_turn=unused,
            ),
        }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with mock.patch.object(socket.socket, "connect", _no_network), \
         mock.patch.object(socket, "create_connection", _no_network):
        graphs = _graphs()
        for name, graph in graphs.items():
            path = OUTPUT_DIR / f"{name}.mmd"
            path.write_text(graph.get_graph(xray=True).draw_mermaid(), encoding="utf-8")
            print(f"wrote {path.relative_to(OUTPUT_DIR.parents[2])}")


if __name__ == "__main__":
    main()
