
import pytest

from unittest.mock import MagicMock, patch

from src.agents.classifier import (
    classify_ticket,
    TicketClassification
)


# ==========================================
# MOCK CLASSIFICATION RESULT
# ==========================================

@pytest.fixture
def mock_classification():

    return TicketClassification(
        category="Network",
        issue_type="VPN Connection Failure",
        impact="Medium",
        urgency="Medium",
        summary=(
            "Employee cannot connect to "
            "the company VPN."
        )
    )


# ==========================================
# TEST 1: SUCCESSFUL CLASSIFICATION
# ==========================================

def test_successful_classification(
    mock_classification
):

    mock_classifier = MagicMock()

    mock_chain = MagicMock()

    mock_chain.invoke.return_value = (
        mock_classification
    )

    # Patch the classifier factory
    with patch(
        "src.agents.classifier.get_classifier",
        return_value=mock_classifier
    ):

        # Patch prompt construction
        with patch(
            "src.agents.classifier.ChatPromptTemplate.from_messages"
        ) as mock_prompt:

            mock_prompt.return_value.__or__.return_value = (
                mock_chain
            )

            result = classify_ticket(
                "My VPN is not connecting."
            )

    assert result.category == "Network"
    assert result.issue_type == "VPN Connection Failure"
    assert result.impact == "Medium"
    assert result.urgency == "Medium"

    assert "VPN" in result.summary

    mock_chain.invoke.assert_called_once()


# ==========================================
# TEST 2: EMPTY TICKET
# ==========================================

def test_empty_ticket():

    with pytest.raises(
        ValueError,
        match="Ticket description cannot be empty"
    ):

        classify_ticket("")


# ==========================================
# TEST 3: INVALID TICKET TYPE
# ==========================================

def test_invalid_ticket_type():

    with pytest.raises(
        ValueError,
        match="Ticket description must be text"
    ):

        classify_ticket(12345)


# ==========================================
# TEST 4: API ERROR PROPAGATION
# ==========================================

def test_api_error_propagation():

    mock_classifier = MagicMock()

    mock_chain = MagicMock()

    mock_chain.invoke.side_effect = RuntimeError(
        "Simulated API failure"
    )

    with patch(
        "src.agents.classifier.get_classifier",
        return_value=mock_classifier
    ):

        with patch(
            "src.agents.classifier.ChatPromptTemplate.from_messages"
        ) as mock_prompt:

            mock_prompt.return_value.__or__.return_value = (
                mock_chain
            )

            with pytest.raises(
                RuntimeError,
                match="Simulated API failure"
            ):

                classify_ticket(
                    "My VPN is not connecting."
                )
