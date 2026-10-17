from langchain_core.messages import HumanMessage

from app.agents.chat.graph import (
    build_conversation_graph,
)

SIM_ID = "06bf8803-c67a-4d77-be3f-ecf622e2de53"

graph = build_conversation_graph(
    SIM_ID,
    "test-user"
)

config = {
    "configurable": {
        "thread_id": f"{SIM_ID}:chat"
    }
}


def ask(question):

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=question)
            ],
            "simulation_id": SIM_ID,
        },
        config=config,
    )

    print(
        question,
        "->",
        result.get("next_step"),
        result.get("last_date_discussed"),
    )

    print(
        "   reply:",
        result["messages"][-1].content
        if result["messages"][-1].type == "ai"
        else None,
    )


ask("Why did it sell on day 16?")

ask("And the next day?")

ask("Why did it do that?")