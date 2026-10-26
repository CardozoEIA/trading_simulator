from langgraph.graph import MessagesState


class SupervisorState(MessagesState):
    simulation_id: str
    last_date_discussed: str | None
    # "explain_agent" | "insights_agent" | "answer" | "conceptual" | "propose_change" | "compare"
    # | "off_topic" | "clarify"
    next_step: str | None
    # Set only for "propose_change". Never applied automatically: the student must confirm.
    proposed_change: dict | None
    # Set only for "compare": the other simulation (owned by the same student) to compare with.
    compare_with: str | None
