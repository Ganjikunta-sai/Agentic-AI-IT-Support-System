
import pytest

from src.workflow.nodes import (
    route_after_classification
)

from src.workflow.graph import (
    check_escalation,
    create_initial_state
)


# ==========================================
# TEST 1: SUCCESSFUL CLASSIFICATION
# ==========================================

def test_successful_classification_route():

    state = {
        "classification_failed": False
    }

    route = route_after_classification(state)

    assert route == "priority"


# ==========================================
# TEST 2: CLASSIFICATION FAILURE
# ==========================================

def test_classification_failure_route():

    state = {
        "classification_failed": True
    }

    route = route_after_classification(state)

    assert route == "human_review"


# ==========================================
# TEST 3: CRITICAL PRIORITY ESCALATION
# ==========================================

def test_critical_priority_escalation():

    state = {
        "priority": "Critical",
        "needs_human_review": False
    }

    route = check_escalation(state)

    assert route == "human_review"


# ==========================================
# TEST 4: LOW CONFIDENCE ESCALATION
# ==========================================

def test_low_confidence_escalation():

    state = {
        "priority": "Medium",
        "needs_human_review": True,
        "confidence": "Low"
    }

    route = check_escalation(state)

    assert route == "human_review"


# ==========================================
# TEST 5: NORMAL COMPLETION
# ==========================================

def test_normal_completion():

    state = {
        "priority": "Medium",
        "needs_human_review": False,
        "confidence": "High"
    }

    route = check_escalation(state)

    assert route == "complete"


# ==========================================
# TEST 6: INITIAL TICKET STATE
# ==========================================

def test_initial_state():

    ticket_text = (
        "My VPN is not connecting."
    )

    state = create_initial_state(
        ticket_text
    )

    assert state["ticket_text"] == ticket_text

    assert state["status"] == "Processing"

    assert state["classification_failed"] is False

    assert state["needs_human_review"] is False

    assert state["recommended_steps"] == []

    assert state["priority"] is None
