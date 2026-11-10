
import uuid

import pytest

from src.workflow.graph import (
    build_support_graph,
    process_ticket,
    resume_ticket,
    recover_ticket,
)
from src.workflow.checkpointer import get_checkpointer

from src.database.crud import (
    save_ticket,
    get_ticket_by_id,
    update_ticket,
)


# ============================================================
# TEST COMPLETE TICKET LIFECYCLE
# ============================================================

@pytest.mark.integration
def test_complete_ticket_lifecycle():

    ticket_id = "T-" + uuid.uuid4().hex[:8].upper()

    employee_name = "Integration Test Employee"

    issue = (
        "The entire department cannot access "
        "the company network. VPN connections "
        "are failing for all employees."
    )

    # --------------------------------------------------------
    # STEP 1: EXECUTE LANGGRAPH WORKFLOW
    # --------------------------------------------------------

    with get_checkpointer() as checkpointer:

        graph = build_support_graph(checkpointer)

        result, config = process_ticket(
            ticket_text=issue,
            thread_id=ticket_id,
            app=graph,
        )

        snapshot = graph.get_state(config)

        # Checkpoint state is authoritative, including
        # when LangGraph returns an interrupt payload.
        workflow_state = dict(snapshot.values)

        assert workflow_state["ticket_text"] == issue

        assert workflow_state["category"] in [
            "Network",
            "Account",
            "Software",
            "Access",
            "Other",
        ]

        assert workflow_state["status"]

        # ----------------------------------------------------
        # STEP 2: SAVE TICKET TO POSTGRESQL
        # ----------------------------------------------------

        database_result = dict(workflow_state)

        if snapshot.next:

            database_result["status"] = (
                "Waiting for Human Review"
            )

            database_result["needs_human_review"] = True

        save_ticket(
            ticket_id=ticket_id,
            employee_name=employee_name,
            issue=issue,
            result=database_result,
        )

    # --------------------------------------------------------
    # STEP 3: VERIFY DATABASE STORAGE
    # --------------------------------------------------------

    saved_ticket = get_ticket_by_id(ticket_id)

    assert saved_ticket is not None
    assert saved_ticket.ticket_id == ticket_id
    assert saved_ticket.employee_name == employee_name
    assert saved_ticket.issue == issue

    # --------------------------------------------------------
    # STEP 4: RECOVER WORKFLOW FROM NEW CONNECTION
    # --------------------------------------------------------

    with get_checkpointer() as checkpointer:

        graph = build_support_graph(checkpointer)

        recovered, config = recover_ticket(
            app=graph,
            thread_id=ticket_id,
        )

        assert recovered.values["ticket_text"] == issue

        # ----------------------------------------------------
        # STEP 5: ADMINISTRATOR APPROVAL WHEN PAUSED
        # ----------------------------------------------------

        if "human_review" in recovered.next:

            resume_ticket(
                app=graph,
                config=config,
                decision="approve",
            )

            final_snapshot = graph.get_state(config)

            assert final_snapshot.next == ()

            final_state = dict(final_snapshot.values)

            assert final_state["human_decision"] == "Approved"

            update_ticket(
                ticket_id=ticket_id,
                result=final_state,
            )

    # --------------------------------------------------------
    # STEP 6: VERIFY FINAL DATABASE RECORD
    # --------------------------------------------------------

    final_ticket = get_ticket_by_id(ticket_id)

    assert final_ticket is not None

    assert final_ticket.status != "Processing"

    print("\n================================")
    print("END-TO-END INTEGRATION RESULT")
    print("================================")

    print("Ticket ID:", final_ticket.ticket_id)
    print("Category:", final_ticket.category)
    print("Priority:", final_ticket.priority)
    print("Confidence:", final_ticket.confidence)
    print("Status:", final_ticket.status)
    print("Human Decision:", final_ticket.human_decision)

    print("\nIntegration test completed successfully.")
