
import uuid

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from src.workflow.state import SupportTicketState
from src.workflow.graph import human_review_node
from src.workflow.checkpointer import get_checkpointer


# ============================================================
# CREATE TEST GRAPH
# ============================================================

def build_test_graph(checkpointer):

    workflow = StateGraph(SupportTicketState)

    workflow.add_node(
        "human_review",
        human_review_node
    )

    workflow.add_edge(START, "human_review")
    workflow.add_edge("human_review", END)

    return workflow.compile(
        checkpointer=checkpointer
    )


# ============================================================
# SAMPLE SUPPORT TICKET
# ============================================================

def create_test_ticket():

    return {
        "ticket_text": (
            "The entire company network is down."
        ),
        "category": "Network",
        "issue_type": "Network Outage",
        "impact": "High",
        "urgency": "High",
        "summary": "Company-wide network outage.",
        "priority": "Critical",
        "priority_reason": (
            "High impact and High urgency."
        ),
        "recommended_steps": [
            "Contact the network administrator."
        ],
        "explanation": (
            "Critical network outage requires review."
        ),
        "confidence": "High",
        "needs_human_review": True,
        "escalation_reason": (
            "Critical network outage."
        ),
        "sources": [],
        "status": "Escalation Required",
        "error": None,
        "human_decision": None,
        "classification_failed": False
    }


# ============================================================
# TEST 1: SAVE INTERRUPTED WORKFLOW
# ============================================================

def test_postgres_checkpoint_recovery():

    thread_id = (
        "TEST-RECOVERY-" + uuid.uuid4().hex[:8]
    )

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    ticket = create_test_ticket()

    # First connection: start and pause workflow
    with get_checkpointer() as checkpointer:

        graph = build_test_graph(checkpointer)

        graph.invoke(ticket, config=config)

        snapshot = graph.get_state(config)

        assert snapshot.next == ("human_review",)

        assert snapshot.values["priority"] == "Critical"

        print("\nWorkflow saved to PostgreSQL.")
        print("Thread ID:", thread_id)

    # First connection has been closed

    # Second connection: recover saved workflow
    with get_checkpointer() as checkpointer:

        graph = build_test_graph(checkpointer)

        snapshot = graph.get_state(config)

        assert snapshot.values["ticket_text"] == (
            "The entire company network is down."
        )

        assert snapshot.next == ("human_review",)

        print("\nWorkflow recovered successfully.")

        # Resume interrupted workflow
        graph.invoke(
            Command(
                resume={
                    "decision": "approve"
                }
            ),
            config=config
        )

        final_snapshot = graph.get_state(config)

        assert final_snapshot.next == ()

        assert final_snapshot.values[
            "human_decision"
        ] == "Approved"

        assert final_snapshot.values["status"] == (
            "Human Approved - Ready for IT Action"
        )

        print("\nAdministrator approval completed.")
        print(
            "Final Status:",
            final_snapshot.values["status"]
        )


# ============================================================
# TEST 2: DIFFERENT THREADS REMAIN ISOLATED
# ============================================================

def test_postgres_thread_isolation():

    thread_id_1 = (
        "TEST-ISOLATION-A-" + uuid.uuid4().hex
    )

    thread_id_2 = (
        "TEST-ISOLATION-B-" + uuid.uuid4().hex
    )

    config1 = {
        "configurable": {
            "thread_id": thread_id_1
        }
    }

    config2 = {
        "configurable": {
            "thread_id": thread_id_2
        }
    }

    ticket1 = create_test_ticket()

    ticket2 = {
        **create_test_ticket(),
        "ticket_text": (
            "VPN authentication failed for an employee."
        )
    }

    with get_checkpointer() as checkpointer:

        graph = build_test_graph(checkpointer)

        graph.invoke(ticket1, config=config1)
        graph.invoke(ticket2, config=config2)

        snapshot1 = graph.get_state(config1)
        snapshot2 = graph.get_state(config2)

        assert snapshot1.values["ticket_text"] == (
            "The entire company network is down."
        )

        assert snapshot2.values["ticket_text"] == (
            "VPN authentication failed for an employee."
        )

        assert snapshot1.next == ("human_review",)
        assert snapshot2.next == ("human_review",)

        print("\nThread isolation verified.")
