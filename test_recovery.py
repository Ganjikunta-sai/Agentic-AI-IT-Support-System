
from src.workflow.graph import (
    build_support_graph,
    recover_ticket
)

from src.workflow.checkpointer import get_checkpointer


with get_checkpointer() as checkpointer:

    app = build_support_graph(checkpointer)

    snapshot, config = recover_ticket(
        app=app,
        thread_id="TEST-POSTGRES-001"
    )

    print("\nRECOVERED TICKET")
    print("====================")

    print(
        "Ticket:",
        snapshot.values.get("ticket_text")
    )

    print(
        "Status:",
        snapshot.values.get("status")
    )

    print(
        "Priority:",
        snapshot.values.get("priority")
    )

    print(
        "Pending nodes:",
        snapshot.next
    )
