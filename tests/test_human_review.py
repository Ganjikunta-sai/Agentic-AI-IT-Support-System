
import uuid

import pytest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from src.workflow.state import SupportTicketState
from src.workflow.graph import human_review_node


# ============================================================
# CREATE TEST LANGGRAPH WORKFLOW
# ============================================================

@pytest.fixture
def review_graph():

    workflow = StateGraph(SupportTicketState)

    workflow.add_node(
        "human_review",
        human_review_node
    )

    workflow.add_edge(
        START,
        "human_review"
    )

    workflow.add_edge(
        "human_review",
        END
    )

    return workflow.compile(
        checkpointer=InMemorySaver()
    )


# ============================================================
# SAMPLE CRITICAL SUPPORT TICKET
# ============================================================

@pytest.fixture
def critical_ticket():

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
            "Contact the network administrator.",
            "Check network infrastructure.",
            "Escalate the outage to IT support."
        ],
        "explanation": (
            "Company-wide outage requires "
            "immediate administrator review."
        ),
        "confidence": "High",
        "needs_human_review": True,
        "escalation_reason": (
            "Critical network outage."
        ),
        "sources": [
            "network_troubleshooting.txt"
        ],
        "status": "Escalation Required",
        "error": None,
        "human_decision": None,
        "classification_failed": False
    }


# ============================================================
# HELPER: GENERATE UNIQUE THREAD CONFIGURATION
# ============================================================

def create_test_config():

    return {
        "configurable": {
            "thread_id": str(uuid.uuid4())
        }
    }


# ============================================================
# TEST 1: LANGGRAPH INTERRUPT
# ============================================================

def test_workflow_interrupt(
    review_graph,
    critical_ticket
):

    config = create_test_config()

    review_graph.invoke(
        critical_ticket,
        config=config
    )

    snapshot = review_graph.get_state(config)

    assert snapshot.next == ("human_review",)

    assert snapshot.values["priority"] == "Critical"

    assert snapshot.values["needs_human_review"] is True

    assert snapshot.values["human_decision"] is None


# ============================================================
# TEST 2: ADMINISTRATOR APPROVAL
# ============================================================

def test_administrator_approval(
    review_graph,
    critical_ticket
):

    config = create_test_config()

    # Start workflow and pause for human review
    review_graph.invoke(
        critical_ticket,
        config=config
    )

    # Resume with administrator approval
    result = review_graph.invoke(
        Command(
            resume={
                "decision": "approve"
            }
        ),
        config=config
    )

    assert result["human_decision"] == "Approved"

    assert result["status"] == (
        "Human Approved - Ready for IT Action"
    )

    assert result["needs_human_review"] is False

    snapshot = review_graph.get_state(config)

    assert snapshot.next == ()

    assert snapshot.values["human_decision"] == "Approved"


# ============================================================
# TEST 3: ADMINISTRATOR REJECTION
# ============================================================

def test_administrator_rejection(
    review_graph,
    critical_ticket
):

    config = create_test_config()

    review_graph.invoke(
        critical_ticket,
        config=config
    )

    result = review_graph.invoke(
        Command(
            resume={
                "decision": "reject"
            }
        ),
        config=config
    )

    assert result["human_decision"] == "Rejected"

    assert result["status"] == (
        "Human Rejected - Further Investigation Required"
    )

    assert result["needs_human_review"] is True

    snapshot = review_graph.get_state(config)

    assert snapshot.next == ()

    assert snapshot.values["human_decision"] == "Rejected"


# ============================================================
# TEST 4: CLASSIFICATION FAILURE APPROVAL
# ============================================================

def test_classification_failure_approval(
    review_graph,
    critical_ticket
):

    ticket = {
        **critical_ticket,
        "classification_failed": True,
        "category": "Other",
        "priority": None,
        "priority_reason": (
            "Classification failed."
        ),
        "status": "Escalation Required"
    }

    config = create_test_config()

    review_graph.invoke(
        ticket,
        config=config
    )

    result = review_graph.invoke(
        Command(
            resume={
                "decision": "approve"
            }
        ),
        config=config
    )

    assert result["human_decision"] == "Approved"

    assert result["status"] == (
        "Human Review Accepted - Manual Classification Required"
    )

    assert result["needs_human_review"] is True

    snapshot = review_graph.get_state(config)

    assert snapshot.next == ()


# ============================================================
# TEST 5: INVALID ADMINISTRATOR DECISION
# ============================================================

def test_invalid_administrator_decision(
    review_graph,
    critical_ticket
):

    config = create_test_config()

    review_graph.invoke(
        critical_ticket,
        config=config
    )

    with pytest.raises(
        ValueError,
        match="Invalid decision"
    ):

        review_graph.invoke(
            Command(
                resume={
                    "decision": "maybe"
                }
            ),
            config=config
        )


# ============================================================
# TEST 6: DIFFERENT TICKETS HAVE DIFFERENT THREADS
# ============================================================

def test_unique_ticket_threads(
    review_graph,
    critical_ticket
):

    config1 = create_test_config()
    config2 = create_test_config()

    review_graph.invoke(
        critical_ticket,
        config=config1
    )

    second_ticket = {
        **critical_ticket,
        "ticket_text": (
            "VPN authentication failed."
        )
    }

    review_graph.invoke(
        second_ticket,
        config=config2
    )

    snapshot1 = review_graph.get_state(config1)
    snapshot2 = review_graph.get_state(config2)

    assert config1["configurable"]["thread_id"] != (
        config2["configurable"]["thread_id"]
    )

    assert snapshot1.values["ticket_text"] == (
        "The entire company network is down."
    )

    assert snapshot2.values["ticket_text"] == (
        "VPN authentication failed."
    )

    assert snapshot1.next == ("human_review",)
    assert snapshot2.next == ("human_review",)
