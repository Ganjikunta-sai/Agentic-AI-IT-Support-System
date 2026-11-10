
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

from src.workflow.state import SupportTicketState

from src.workflow.nodes import (
    classification_node,
    priority_node,
    resolution_node,
    route_after_classification
)

from src.workflow.checkpointer import get_checkpointer


# ==================================================
# ROUTE AFTER RESOLUTION
# ==================================================

def check_escalation(state):

    if state.get("priority") == "Critical":
        return "human_review"

    if state.get("needs_human_review", False):
        return "human_review"

    return "complete"


# ==================================================
# HUMAN REVIEW NODE
# ==================================================

def human_review_node(state):

    print("\nWaiting for IT administrator review...")

    human_response = interrupt({
        "message": "This ticket requires human review.",
        "ticket": state["ticket_text"],
        "category": state.get("category"),
        "priority": state.get("priority"),
        "recommended_steps": state.get(
            "recommended_steps", []
        ),
        "explanation": state.get("explanation"),
        "escalation_reason": state.get(
            "escalation_reason"
        ),
        "question": "Approve or reject this recommendation?"
    })

    if not isinstance(human_response, dict):
        raise ValueError(
            "Human response must be a dictionary."
        )

    decision = str(
        human_response.get("decision", "")
    ).strip().lower()

    if decision == "approve":

        if state.get("classification_failed", False):

            return {
                "human_decision": "Approved",
                "status": (
                    "Human Review Accepted - "
                    "Manual Classification Required"
                ),
                "needs_human_review": True
            }

        return {
            "human_decision": "Approved",
            "status": "Human Approved - Ready for IT Action",
            "needs_human_review": False
        }

    elif decision == "reject":

        return {
            "human_decision": "Rejected",
            "status": (
                "Human Rejected - "
                "Further Investigation Required"
            ),
            "needs_human_review": True
        }

    else:

        raise ValueError(
            "Invalid decision. Enter approve or reject."
        )


# ==================================================
# BUILD LANGGRAPH WORKFLOW
# ==================================================

def build_support_graph(checkpointer):

    workflow = StateGraph(SupportTicketState)

    # Create nodes
    workflow.add_node(
        "classification",
        classification_node
    )

    workflow.add_node(
        "priority",
        priority_node
    )

    workflow.add_node(
        "resolution",
        resolution_node
    )

    workflow.add_node(
        "human_review",
        human_review_node
    )

    # Starting point
    workflow.add_edge(
        START,
        "classification"
    )

    # If classification fails, escalate immediately
    workflow.add_conditional_edges(
        "classification",
        route_after_classification,
        {
            "priority": "priority",
            "human_review": "human_review"
        }
    )

    # Successful classification -> priority
    workflow.add_edge(
        "priority",
        "resolution"
    )

    # Resolution -> complete or human review
    workflow.add_conditional_edges(
        "resolution",
        check_escalation,
        {
            "human_review": "human_review",
            "complete": END
        }
    )

    # Human review -> end
    workflow.add_edge(
        "human_review",
        END
    )

    # Compile graph with PostgreSQL checkpoint storage
    app = workflow.compile(
        checkpointer=checkpointer
    )

    return app


# ==================================================
# INITIAL TICKET STATE
# ==================================================

def create_initial_state(ticket_text):

    return {
        "ticket_text": ticket_text,
        "category": None,
        "issue_type": None,
        "impact": None,
        "urgency": None,
        "summary": None,
        "priority": None,
        "priority_reason": None,
        "recommended_steps": [],
        "explanation": None,
        "confidence": None,
        "needs_human_review": False,
        "escalation_reason": None,
        "sources": [],
        "status": "Processing",
        "error": None,
        "human_decision": None,
        "classification_failed": False
    }


# ==================================================
# PROCESS NEW TICKET
# ==================================================

def process_ticket(
    ticket_text,
    thread_id,
    app
):

    initial_state = create_initial_state(
        ticket_text
    )

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = app.invoke(
        initial_state,
        config=config
    )

    return result, config


# ==================================================
# RESUME HUMAN REVIEW
# ==================================================

def resume_ticket(
    app,
    config,
    decision
):

    decision = decision.strip().lower()

    if decision not in ["approve", "reject"]:
        raise ValueError(
            "Decision must be approve or reject."
        )

    result = app.invoke(
        Command(
            resume={"decision": decision}
        ),
        config=config
    )

    return result


# ==================================================
# RECOVER PREVIOUS TICKET
# ==================================================

def recover_ticket(
    app,
    thread_id
):

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    snapshot = app.get_state(config)

    if not snapshot.values:
        raise ValueError(
            f"No saved workflow found for {thread_id}"
        )

    return snapshot, config


# ==================================================
# DISPLAY TICKET RESULT
# ==================================================

def display_result(result):

    print("\n================================")
    print("       IT SUPPORT TICKET RESULT")
    print("================================")

    print("\nTicket:", result.get("ticket_text"))

    print("\nCLASSIFICATION")
    print("Category:", result.get("category"))
    print("Issue Type:", result.get("issue_type"))
    print("Impact:", result.get("impact"))
    print("Urgency:", result.get("urgency"))

    print("\nPRIORITY")
    print("Priority:", result.get("priority"))
    print("Reason:", result.get("priority_reason"))

    print("\nRESOLUTION")
    for step in result.get("recommended_steps", []):
        print("-", step)

    print("Explanation:", result.get("explanation"))
    print("Confidence:", result.get("confidence"))

    print("\nHUMAN REVIEW")
    print("Human Decision:", result.get("human_decision"))
    print(
        "Needs Human Review:",
        result.get("needs_human_review")
    )
    print(
        "Escalation Reason:",
        result.get("escalation_reason")
    )

    print("\nFINAL STATUS:", result.get("status"))


# ==================================================
# TEST WORKFLOW
# ==================================================

if __name__ == "__main__":

    employee_ticket = (
        "My VPN is not connecting. "
        "I cannot access the company network."
    )

    ticket_id = "TEST-POSTGRES-001"

    # Keep database connection open while graph runs
    with get_checkpointer() as checkpointer:

        app = build_support_graph(checkpointer)

        result, config = process_ticket(
            ticket_text=employee_ticket,
            thread_id=ticket_id,
            app=app
        )

        snapshot = app.get_state(config)

        if snapshot.next:

            print("\nHUMAN REVIEW REQUIRED")

            decision = input(
                "IT Administrator - Enter approve or reject: "
            )

            result = resume_ticket(
                app=app,
                config=config,
                decision=decision
            )

        display_result(result)
