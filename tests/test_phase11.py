
from src.database.ticket_lifecycle import (
    validate_status_transition,
    get_available_statuses,
)


def test_open_to_in_progress():
    assert validate_status_transition(
        "Open", "In Progress"
    )


def test_in_progress_to_resolved():
    assert validate_status_transition(
        "In Progress", "Resolved"
    )


def test_resolved_to_closed():
    assert validate_status_transition(
        "Resolved", "Closed"
    )


def test_closed_cannot_reopen():
    assert not validate_status_transition(
        "Closed", "In Progress"
    )


def test_waiting_review_cannot_resolve():
    assert not validate_status_transition(
        "Waiting for Human Review", "Resolved"
    )


def test_review_in_progress_cannot_close():
    assert not validate_status_transition(
        "Review in Progress", "Closed"
    )


def test_approved_ticket_can_start_work():
    assert "In Progress" in get_available_statuses(
        "Human Approved - Ready for IT Action"
    )


def test_rejected_ticket_can_escalate():
    assert "Escalated" in get_available_statuses(
        "Human Rejected - Further Investigation Required"
    )


def test_in_progress_can_escalate():
    assert validate_status_transition(
        "In Progress", "Escalated"
    )


def test_escalated_ticket_can_resume():
    assert validate_status_transition(
        "Escalated", "In Progress"
    )


def test_invalid_status_is_rejected():
    assert not validate_status_transition(
        "Unknown", "Resolved"
    )


def test_closed_has_no_next_status():
    assert get_available_statuses("Closed") == []
