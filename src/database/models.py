
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    JSON,
    func
)

from src.database.database import Base


class Ticket(Base):

    __tablename__ = "tickets"

    # Unique ticket ID
    ticket_id = Column(String(50), primary_key=True)

    # Employee information
    employee_name = Column(String(100), nullable=False)

    # Ticket details
    issue = Column(Text, nullable=False)
    category = Column(String(50))
    issue_type = Column(String(100))

    # Classification details
    impact = Column(String(20))
    urgency = Column(String(20))
    summary = Column(Text)

    # Priority details
    priority = Column(String(20))
    priority_reason = Column(Text)

    # AI recommendation details
    recommended_steps = Column(JSON, default=list)
    explanation = Column(Text)
    confidence = Column(String(20))

    # Human review details
    needs_human_review = Column(Boolean, default=False)
    escalation_reason = Column(Text)
    human_decision = Column(String(30))

    # Knowledge base sources
    sources = Column(JSON, default=list)

    # Ticket status
    status = Column(String(50), default="Open")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
