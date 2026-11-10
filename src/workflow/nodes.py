
from src.agents.classifier import classify_ticket
from src.agents.priority_engine import assign_priority
from src.agents.resolution_agent import generate_resolution

from src.ingestion.document_loader import load_documents
from src.rag.chunking import split_documents
from src.rag.vector_store import create_vector_store

from src.utils.error_handler import (
    log_info,
    log_warning,
    handle_error
)


# ==========================================
# LOAD KNOWLEDGE BASE
# ==========================================

def get_knowledge_base():

    documents = load_documents()

    if not documents:
        raise ValueError(
            "No knowledge-base documents found."
        )

    chunks = split_documents(documents)

    if not chunks:
        raise ValueError(
            "No document chunks generated."
        )

    return create_vector_store(chunks)


# ==========================================
# CLASSIFICATION NODE
# ==========================================

def classification_node(state):

    log_info("Classification node started.")

    try:

        result = classify_ticket(
            state["ticket_text"]
        )

        log_info(
            f"Ticket classified: {result.category}"
        )

        return {
            "category": result.category,
            "issue_type": result.issue_type,
            "impact": result.impact,
            "urgency": result.urgency,
            "summary": result.summary,
            "classification_failed": False
        }

    except Exception as error:

        handle_error(
            error,
            context="Classification Node"
        )

        log_warning(
            "Classification failed. Human review required."
        )

        return {
            "category": "Other",
            "issue_type": "Unclassified",
            "impact": None,
            "urgency": None,
            "summary": "Automatic classification unavailable.",
            "priority": None,
            "priority_reason": (
                "Priority not assigned because "
                "classification failed."
            ),
            "classification_failed": True,
            "needs_human_review": True,
            "recommended_steps": [],
            "explanation": (
                "The AI classification service is unavailable. "
                "An IT administrator must assess this ticket."
            ),
            "confidence": "Low",
            "escalation_reason": (
                "Automatic ticket classification failed."
            ),
            "sources": [],
            "status": "Escalation Required",
            "error": "Classification service unavailable."
        }


# ==========================================
# PRIORITY NODE
# ==========================================

def priority_node(state):

    result = assign_priority(
        impact=state["impact"],
        urgency=state["urgency"]
    )

    log_info(
        f"Ticket priority assigned: {result.priority}"
    )

    return {
        "priority": result.priority,
        "priority_reason": result.reason
    }


# ==========================================
# RESOLUTION NODE
# ==========================================

def resolution_node(state):

    log_info("Resolution node started.")

    try:

        vector_store = get_knowledge_base()

        recommendation, sources = generate_resolution(
            ticket_text=state["ticket_text"],
            category=state["category"],
            vector_store=vector_store
        )

        needs_review = (
            recommendation.needs_human_review
            or state["priority"] == "Critical"
        )

        escalation_reason = recommendation.escalation_reason

        if state["priority"] == "Critical":

            escalation_reason = (
                "Critical ticket requires "
                "IT administrator review."
            )

        return {
            "recommended_steps": recommendation.recommended_steps,
            "explanation": recommendation.explanation,
            "confidence": recommendation.confidence,
            "needs_human_review": needs_review,
            "escalation_reason": escalation_reason,
            "sources": sources,
            "status": (
                "Escalation Required"
                if needs_review
                else "Recommendation Generated"
            )
        }

    except Exception as error:

        handle_error(
            error,
            context="Resolution Node"
        )

        return {
            "recommended_steps": [],
            "explanation": (
                "Automatic resolution is unavailable. "
                "IT support must investigate."
            ),
            "confidence": "Low",
            "needs_human_review": True,
            "escalation_reason": (
                "Resolution generation failed."
            ),
            "sources": [],
            "status": "Escalation Required",
            "error": "Resolution service unavailable."
        }


# ==========================================
# CLASSIFICATION FAILURE ROUTING
# ==========================================

def route_after_classification(state):

    if state.get("classification_failed", False):
        return "human_review"

    return "priority"
