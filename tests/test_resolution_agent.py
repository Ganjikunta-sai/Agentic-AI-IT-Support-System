
import pytest

from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from src.agents.resolution_agent import (
    ResolutionRecommendation,
    generate_resolution
)


# ==========================================
# MOCK KNOWLEDGE-BASE DOCUMENT
# ==========================================

@pytest.fixture
def mock_documents():

    return [
        Document(
            page_content=(
                "For VPN authentication failure, "
                "verify the employee account status. "
                "If the password has expired, follow "
                "the approved password reset process."
            ),
            metadata={
                "source": "vpn_troubleshooting.txt"
            }
        )
    ]


# ==========================================
# TEST 1: SUCCESSFUL RESOLUTION
# ==========================================

def test_successful_resolution(mock_documents):

    recommendation = ResolutionRecommendation(
        recommended_steps=[
            "Verify the employee account status.",
            "Follow the approved password reset process "
            "if the password has expired."
        ],
        explanation=(
            "The official VPN guide provides "
            "authentication troubleshooting steps."
        ),
        confidence="High",
        needs_human_review=False,
        escalation_reason=""
    )

    with (
        patch(
            "src.agents.resolution_agent.search_documents",
            return_value=mock_documents
        ),
        patch(
            "src.agents.resolution_agent.search_similar_tickets",
            return_value=[]
        ),
        patch(
            "src.agents.resolution_agent.get_resolution_llm",
            return_value=MagicMock()
        ),
        patch(
            "src.agents.resolution_agent.invoke_resolution_chain",
            return_value=recommendation
        )
    ):

        result, sources = generate_resolution(
            ticket_text="My VPN authentication is failing.",
            category="Network",
            vector_store=MagicMock()
        )

    assert result.confidence == "High"
    assert result.needs_human_review is False
    assert len(result.recommended_steps) == 2
    assert sources == ["vpn_troubleshooting.txt"]


# ==========================================
# TEST 2: NO DOCUMENTS RETRIEVED
# ==========================================

def test_no_documents():

    with patch(
        "src.agents.resolution_agent.search_documents",
        return_value=[]
    ):

        result, sources = generate_resolution(
            ticket_text="Unknown technical issue",
            category="Other",
            vector_store=MagicMock()
        )

    assert result.recommended_steps == []
    assert result.confidence == "Low"
    assert result.needs_human_review is True
    assert result.escalation_reason
    assert sources == []


# ==========================================
# TEST 3: LOW CONFIDENCE ESCALATION
# ==========================================

def test_low_confidence_escalation(mock_documents):

    recommendation = ResolutionRecommendation(
        recommended_steps=[
            "Verify the employee account status."
        ],
        explanation="The available evidence is limited.",
        confidence="Low",
        needs_human_review=False,
        escalation_reason=""
    )

    with (
        patch(
            "src.agents.resolution_agent.search_documents",
            return_value=mock_documents
        ),
        patch(
            "src.agents.resolution_agent.search_similar_tickets",
            return_value=[]
        ),
        patch(
            "src.agents.resolution_agent.get_resolution_llm",
            return_value=MagicMock()
        ),
        patch(
            "src.agents.resolution_agent.invoke_resolution_chain",
            return_value=recommendation
        )
    ):

        result, sources = generate_resolution(
            ticket_text="My VPN is failing.",
            category="Network",
            vector_store=MagicMock()
        )

    assert result.confidence == "Low"
    assert result.needs_human_review is True
    assert result.escalation_reason != ""


# ==========================================
# TEST 4: EMPTY RECOMMENDATION
# ==========================================

def test_empty_recommendation(mock_documents):

    recommendation = ResolutionRecommendation(
        recommended_steps=[],
        explanation="Insufficient troubleshooting evidence.",
        confidence="Medium",
        needs_human_review=False,
        escalation_reason=""
    )

    with (
        patch(
            "src.agents.resolution_agent.search_documents",
            return_value=mock_documents
        ),
        patch(
            "src.agents.resolution_agent.search_similar_tickets",
            return_value=[]
        ),
        patch(
            "src.agents.resolution_agent.get_resolution_llm",
            return_value=MagicMock()
        ),
        patch(
            "src.agents.resolution_agent.invoke_resolution_chain",
            return_value=recommendation
        )
    ):

        result, sources = generate_resolution(
            ticket_text="My VPN is failing.",
            category="Network",
            vector_store=MagicMock()
        )

    assert result.recommended_steps == []
    assert result.needs_human_review is True
    assert result.escalation_reason


# ==========================================
# TEST 5: API FAILURE PROPAGATION
# ==========================================

def test_api_failure(mock_documents):

    with (
        patch(
            "src.agents.resolution_agent.search_documents",
            return_value=mock_documents
        ),
        patch(
            "src.agents.resolution_agent.search_similar_tickets",
            return_value=[]
        ),
        patch(
            "src.agents.resolution_agent.get_resolution_llm",
            return_value=MagicMock()
        ),
        patch(
            "src.agents.resolution_agent.invoke_resolution_chain",
            side_effect=RuntimeError(
                "Simulated Groq API failure"
            )
        )
    ):

        with pytest.raises(
            RuntimeError,
            match="Simulated Groq API failure"
        ):

            generate_resolution(
                ticket_text="My VPN is failing.",
                category="Network",
                vector_store=MagicMock()
            )
