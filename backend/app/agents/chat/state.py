from langgraph.graph import MessagesState


class SupervisorState(MessagesState):
    simulation_id: str
    last_date_discussed: str | None
    # "explain_agent" | "insights_agent" | "answer" | "conceptual" | "propose_change" | "clarify"
    next_step: str | None
    # Set only for "propose_change". Never applied automatically: the student must confirm.
    proposed_change: dict | None