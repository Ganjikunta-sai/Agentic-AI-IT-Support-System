
from unittest.mock import patch

from src.workflow.graph import process_ticket


def simulated_failure(ticket_text):
    raise RuntimeError("Simulated Groq API outage")


with patch(
    "src.workflow.nodes.classify_ticket",
    side_effect=simulated_failure
):

    result, app, config = process_ticket(
        ticket_text="My VPN is not connecting.",
        thread_id="TEST-CLASSIFICATION-FAILURE"
    )

    snapshot = app.get_state(config)

    assert result["classification_failed"] is True
    assert result["priority"] is None
    assert result["needs_human_review"] is True
    assert snapshot.next == ("human_review",)

    print("\nCLASSIFICATION FAILURE TEST PASSED")
    print("Category:", result["category"])
    print("Priority:", result["priority"])
    print("Status:", result["status"])
    print("Escalation:", result["escalation_reason"])
    print("Pending node:", snapshot.next)
