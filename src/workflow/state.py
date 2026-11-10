
from typing import TypedDict, List, Optional


class SupportTicketState(TypedDict):

    ticket_text: str

    category: Optional[str]
    issue_type: Optional[str]

    impact: Optional[str]
    urgency: Optional[str]

    summary: Optional[str]

    priority: Optional[str]
    priority_reason: Optional[str]

    recommended_steps: List[str]
    explanation: Optional[str]

    confidence: Optional[str]

    needs_human_review: bool
    escalation_reason: Optional[str]

    sources: List[str]

    status: str
    error: Optional[str]

    human_decision: Optional[str]

    # New field for classification failures
    classification_failed: bool
