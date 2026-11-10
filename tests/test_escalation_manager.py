
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.utils.escalation_manager import escalate_ticket


def create_mock_session(status="In Progress"):

    session = MagicMock()

    session.get.return_value = SimpleNamespace(
        ticket_id="T-TEST001",
        status=status,
    )

    session.execute.return_value.rowcount = 1

    return session


def test_escalation_success():

    session = create_mock_session()

    with patch(
        "src.utils.escalation_manager.SessionLocal",
        return_value=session,
    ):

        result = escalate_ticket(
            "T-TEST001",
            "VPN issue unresolved",
        )

    assert result["status"] == "Escalated"
    assert result["reason"] == "VPN issue unresolved"

    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_empty_escalation_reason():

    with pytest.raises(ValueError):
        escalate_ticket("T-TEST001", "")


def test_ticket_not_found():

    session = create_mock_session()
    session.get.return_value = None

    with patch(
        "src.utils.escalation_manager.SessionLocal",
        return_value=session,
    ):

        with pytest.raises(ValueError):
            escalate_ticket(
                "T-MISSING",
                "Needs investigation",
            )

    session.rollback.assert_called_once()
    session.close.assert_called_once()


def test_closed_ticket_cannot_escalate():

    session = create_mock_session("Closed")

    with patch(
        "src.utils.escalation_manager.SessionLocal",
        return_value=session,
    ):

        with pytest.raises(ValueError):
            escalate_ticket(
                "T-TEST001",
                "Further investigation",
            )

    session.commit.assert_not_called()


def test_concurrent_status_change():

    session = create_mock_session()
    session.execute.return_value.rowcount = 0

    with patch(
        "src.utils.escalation_manager.SessionLocal",
        return_value=session,
    ):

        with pytest.raises(RuntimeError):
            escalate_ticket(
                "T-TEST001",
                "VPN issue unresolved",
            )

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_database_failure():

    session = create_mock_session()

    session.execute.side_effect = RuntimeError(
        "Database unavailable"
    )

    with patch(
        "src.utils.escalation_manager.SessionLocal",
        return_value=session,
    ):

        with pytest.raises(RuntimeError):
            escalate_ticket(
                "T-TEST001",
                "Needs investigation",
            )

    session.rollback.assert_called_once()
    session.close.assert_called_once()
