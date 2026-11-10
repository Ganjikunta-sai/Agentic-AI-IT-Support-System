"""AI IT Support Desk: authenticated Employee and IT Desk portals.

Run: streamlit run app.py
Human support states are stored separately from legacy LangGraph ticket statuses.
"""
from __future__ import annotations

import uuid
from collections import Counter

import streamlit as st

from src.auth.database import initialize_auth_database
from src.auth.employee_management import (
    initialize_employee_management, list_employees, deactivate_employee,
    reactivate_employee, soft_delete_employee, get_employee_account_history,
)
from src.auth.login_ui import render_login_page, render_account_sidebar
from src.auth.session import current_user, require_employee, require_it_staff, require_it_admin
from src.database.ticket_access import (
    initialize_ticket_access, bind_new_ticket_owner, list_employee_ticket_ids,
    require_ticket_access,
)
from src.database.support_workflow import (
    initialize_support_workflow, start_support_case, record_employee_contact,
    resolve_ticket, escalate_ticket as escalate_support_case,
    begin_human_review, add_review_note, get_support_case,
    get_support_history, list_support_cases, SupportStatus,
)
from src.database.crud import save_ticket, get_ticket_by_id, get_all_tickets
from src.database.reconciliation import reconcile_ticket
from src.workflow.graph import build_support_graph, process_ticket
from src.workflow.checkpointer import get_checkpointer
from src.utils.input_validator import validate_ticket
from src.utils.error_handler import handle_error, log_info

st.set_page_config(page_title="AI IT Support Desk", page_icon="🎫", layout="wide")
EMPLOYEE_PAGES = ["Submit Ticket", "My Tickets"]
STAFF_PAGES = ["Overview", "Ticket Management", "Escalation Center", "Workflow Diagnostics"]
ADMIN_PAGES = ["Human Review", "Employee Management"]


@st.cache_resource(show_spinner="Preparing application tables...")
def initialize():
    initialize_auth_database()
    initialize_ticket_access()
    initialize_employee_management()
    initialize_support_workflow()
    return True


def report_error(exc: Exception, context: str):
    try:
        handle_error(exc, context=context)
    except Exception:
        pass
    st.error(f"{context} failed. See server logs for details.")


def safe_action(action, context: str):
    try:
        action()
    except Exception as exc:
        report_error(exc, context)
    else:
        st.success(f"{context} completed.")
        st.rerun()


def ticket_rows(tickets, actor_id: int | None = None):
    rows = []
    for ticket in tickets:
        case = None
        if actor_id is not None:
            case = get_support_case(ticket.ticket_id, actor_id)
        rows.append({
            "Ticket ID": ticket.ticket_id,
            "Employee": ticket.employee_name,
            "Category": ticket.category or "Unassigned",
            "Priority": ticket.priority or "Unassigned",
            "AI Status": ticket.status,
            "Support Status": case["status"] if case else "Not started",
        })
    return rows


def show_details(ticket, support_case=None):
    st.markdown(f"### Ticket {ticket.ticket_id}")
    a, b, c = st.columns(3)
    a.write(f"**Employee:** {ticket.employee_name}")
    b.write(f"**Category:** {ticket.category or 'Unassigned'}")
    c.write(f"**Priority:** {ticket.priority or 'Unassigned'}")
    st.write(f"**AI workflow status:** {ticket.status}")
    if support_case:
        st.write(f"**IT support status:** {support_case['status']}")
        if support_case.get("escalation_reason"):
            st.warning(f"Escalation: {support_case['escalation_reason']}")
        if support_case.get("resolution_note"):
            st.success(f"Resolution: {support_case['resolution_note']}")
    st.write("**Issue:**", ticket.issue)
    st.markdown("#### AI Troubleshooting Recommendation")
    st.write(getattr(ticket, "explanation", None) or "No explanation available.")
    steps = getattr(ticket, "recommended_steps", None) or []
    if isinstance(steps, str):
        steps = [steps]
    for i, step in enumerate(steps, 1):
        st.write(f"{i}. {step}")
    sources = getattr(ticket, "sources", None)
    if sources:
        st.write("**Sources:**", sources)


def create_ticket(employee: dict, issue: str) -> str:
    """Preserve existing LangGraph/RAG execution and save employee ownership."""
    ticket_id = "T-" + uuid.uuid4().hex[:8].upper()
    with get_checkpointer() as checkpointer:
        graph = build_support_graph(checkpointer)
        _, config = process_ticket(ticket_text=issue, thread_id=ticket_id, app=graph)
        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise RuntimeError("No AI workflow state was produced.")
        result = dict(snapshot.values)
        if snapshot.next:
            result["status"] = "Waiting for Human Review"
            result["needs_human_review"] = True
        save_ticket(
            ticket_id=ticket_id,
            employee_name=employee["full_name"],
            issue=issue,
            result=result,
        )
    # Ownership is stored separately; if this fails, staff must reconcile the
    # orphan ticket. Never display an unowned ticket to an employee.
    bind_new_ticket_owner(ticket_id, employee["id"])
    log_info(f"Ticket {ticket_id} created by authenticated employee")
    return ticket_id


def employee_submit_page(user):
    require_employee()
    st.title("Submit IT Support Ticket")
    st.caption(f"Signed in as {user['full_name']} ({user['email']})")
    with st.form("employee_new_ticket", clear_on_submit=False):
        issue = st.text_area("Describe the issue", height=150,
                             placeholder="My VPN is not connecting to the company network...")
        submitted = st.form_submit_button("Submit Ticket", type="primary")
    if submitted:
        valid, message = validate_ticket(user["full_name"], issue)
        if not valid:
            st.warning(message)
        else:
            try:
                with st.spinner("Running classification and RAG troubleshooting..."):
                    ticket_id = create_ticket(user, issue.strip())
                st.session_state["last_ticket_id"] = ticket_id
                st.success(f"Ticket created: {ticket_id}")
            except Exception as exc:
                report_error(exc, "Ticket submission")
    last = st.session_state.get("last_ticket_id")
    if last:
        try:
            require_ticket_access(last, user["id"])
            ticket = get_ticket_by_id(last)
            if ticket:
                show_details(ticket)
        except Exception as exc:
            report_error(exc, "Ticket details")


def employee_tickets_page(user):
    require_employee()
    st.title("My Support Tickets")
    try:
        ids = list_employee_ticket_ids(user["id"])
        tickets = [t for ticket_id in ids if (t := get_ticket_by_id(ticket_id))]
    except Exception as exc:
        report_error(exc, "Load my tickets")
        return
    if not tickets:
        st.info("You have no tickets yet.")
        return
    st.dataframe(ticket_rows(tickets), hide_index=True, use_container_width=True)
    selected = st.selectbox("Select your ticket", [t.ticket_id for t in tickets])
    try:
        require_ticket_access(selected, user["id"])
        ticket = get_ticket_by_id(selected)
        if ticket:
            show_details(ticket)
            st.caption("For status changes, contact the IT Desk. Staff record your confirmation.")
    except Exception as exc:
        report_error(exc, "Ticket access")


def overview_page(user):
    require_it_staff()
    st.title("IT Support Overview")
    try:
        tickets = list(get_all_tickets())
        cases = list_support_cases(user["id"])
        counts = Counter(c["status"] for c in cases)
        a, b, c, d = st.columns(4)
        a.metric("Total Tickets", len(tickets))
        b.metric("Open Support Cases", sum(c["status"] != SupportStatus.RESOLVED.value for c in cases))
        c.metric("Resolved Cases", counts[SupportStatus.RESOLVED.value])
        d.metric("Awaiting Employee", counts[SupportStatus.AWAITING_EMPLOYEE.value])
        st.dataframe(ticket_rows(tickets, user["id"]), hide_index=True, use_container_width=True)
    except Exception as exc:
        report_error(exc, "Overview")


def support_controls(ticket_id: str, user: dict):
    require_it_staff()
    case = get_support_case(ticket_id, user["id"])
    if case is None:
        st.info("Start an IT Desk case to record calls, resolutions and escalations.")
        if st.button("Start Support Case", key=f"start_{ticket_id}"):
            safe_action(lambda: start_support_case(ticket_id, user["id"]), "Start support case")
        return
    status = case["status"]
    st.write("**Support status:**", status)
    if status != SupportStatus.RESOLVED.value:
        with st.form(f"contact_{ticket_id}"):
            contact_note = st.text_area("Call / message notes", key=f"contact_note_{ticket_id}")
            contact = st.form_submit_button("Record Employee Contact")
        if contact:
            safe_action(lambda: record_employee_contact(ticket_id, user["id"], contact_note), "Record contact")
    if status not in {SupportStatus.RESOLVED.value, SupportStatus.ESCALATED.value,
                      SupportStatus.REVIEW_IN_PROGRESS.value}:
        with st.form(f"resolve_{ticket_id}"):
            resolution_note = st.text_area("Resolution details", key=f"resolution_{ticket_id}")
            confirmed = st.checkbox("Employee explicitly confirmed the issue is fixed")
            resolve = st.form_submit_button("Mark Resolved", disabled=not confirmed)
        if resolve:
            safe_action(lambda: resolve_ticket(ticket_id, user["id"], resolution_note,
                                                employee_confirmed=confirmed), "Resolve ticket")
        with st.form(f"escalate_{ticket_id}"):
            reason = st.text_area("Why is this issue still unresolved?")
            escalate = st.form_submit_button("Escalate to Human Review")
        if escalate:
            safe_action(lambda: escalate_support_case(ticket_id, user["id"], reason), "Escalation")
    if status in {SupportStatus.ESCALATED.value, SupportStatus.REVIEW_IN_PROGRESS.value}:
        st.warning("Escalated to IT Admin for Human Review.")
    with st.expander("Support action history"):
        st.dataframe(get_support_history(ticket_id, user["id"]), hide_index=True,
                     use_container_width=True)


def ticket_management_page(user):
    require_it_staff()
    st.title("Ticket Management")
    try:
        tickets = list(get_all_tickets())
        search = st.text_input("Search Ticket ID or Employee")
        filtered = [t for t in tickets if search.casefold() in
                    f"{t.ticket_id} {t.employee_name}".casefold()]
        st.dataframe(ticket_rows(filtered, user["id"]), hide_index=True,
                     use_container_width=True)
        if not filtered:
            st.info("No matching tickets.")
            return
        ids = [t.ticket_id for t in filtered]
        selected = st.selectbox("Select ticket", ids, key="staff_ticket_selection")
        ticket = get_ticket_by_id(selected)
        if ticket:
            case = get_support_case(selected, user["id"])
            show_details(ticket, case)
            st.divider()
            support_controls(selected, user)
    except Exception as exc:
        report_error(exc, "Ticket Management")


def escalation_page(user):
    require_it_staff()
    st.title("Escalation Center")
    try:
        if user["role"] == "it_admin":
            cases = list_support_cases(user["id"])
            cases = [c for c in cases if c["status"] in
                     {SupportStatus.ESCALATED.value, SupportStatus.REVIEW_IN_PROGRESS.value}]
        else:
            # IT Support cannot view the admin-only Human Review queue.
            st.info("Escalated cases are handled by IT Admin. Escalate from Ticket Management.")
            return
        st.metric("Cases requiring review", len(cases))
        st.dataframe(cases, hide_index=True, use_container_width=True)
    except Exception as exc:
        report_error(exc, "Escalation Center")


def human_review_page(user):
    require_it_admin()
    st.title("Human Review")
    try:
        cases = [c for c in list_support_cases(user["id"])
                 if c["status"] in {SupportStatus.ESCALATED.value,
                                     SupportStatus.REVIEW_IN_PROGRESS.value}]
        if not cases:
            st.success("No cases awaiting Human Review.")
            return
        selected = st.selectbox("Select escalated case", [c["ticket_id"] for c in cases])
        case = get_support_case(selected, user["id"])
        ticket = get_ticket_by_id(selected)
        if ticket:
            show_details(ticket, case)
        if case["status"] == SupportStatus.ESCALATED.value:
            with st.form(f"begin_review_{selected}"):
                note = st.text_area("Initial investigation note")
                begin = st.form_submit_button("Begin Human Review")
            if begin:
                safe_action(lambda: begin_human_review(selected, user["id"], note), "Begin review")
        with st.form(f"review_note_{selected}"):
            note = st.text_area("Investigation update")
            add_note = st.form_submit_button("Save Review Note")
        if add_note:
            safe_action(lambda: add_review_note(selected, user["id"], note), "Save review note")
        with st.form(f"admin_resolve_{selected}"):
            resolution = st.text_area("Final resolution details")
            confirmed = st.checkbox("Employee confirmed the issue is resolved", key=f"admin_confirm_{selected}")
            finish = st.form_submit_button("Resolve After Human Review", disabled=not confirmed)
        if finish:
            safe_action(lambda: resolve_ticket(selected, user["id"], resolution,
                                                employee_confirmed=confirmed), "Resolve review")
        st.subheader("Audit history")
        st.dataframe(get_support_history(selected, user["id"]), hide_index=True,
                     use_container_width=True)
    except Exception as exc:
        report_error(exc, "Human Review")


def employee_management_page(user):
    require_it_admin()
    st.title("Employee Management")
    st.caption("Deactivate or soft delete employee accounts without deleting tickets or history.")
    try:
        employees = list_employees(actor_user_id=user["id"])
        if not employees:
            st.info("No visible employee accounts found.")
            return
        st.dataframe([{
            "ID": e["id"], "Name": e["full_name"], "Email": e["email"],
            "Status": "Active" if e["is_active"] else "Inactive",
        } for e in employees], hide_index=True, use_container_width=True)
        employee_ids = [e["id"] for e in employees]
        selected = st.selectbox(
            "Choose employee", employee_ids,
            format_func=lambda x: next(
                f"{e['full_name']} — {e['email']}" for e in employees if e["id"] == x
            ),
        )
        employee = next(e for e in employees if e["id"] == selected)
        action = "Deactivate" if employee["is_active"] else "Reactivate"
        with st.form(f"employee_action_{selected}_{action}"):
            reason = st.text_area(f"Reason for {action.lower()}")
            confirm = st.checkbox(f"I confirm I want to {action.lower()} this employee")
            submit = st.form_submit_button(f"{action} Employee")
        if submit:
            if not confirm:
                st.warning("Check the confirmation box before continuing.")
            elif len(reason.strip()) < 5:
                st.warning("Provide a meaningful reason (at least 5 characters).")
            else:
                fn = deactivate_employee if employee["is_active"] else reactivate_employee
                safe_action(
                    lambda: fn(actor_user_id=user["id"], employee_user_id=selected,
                               reason=reason.strip()),
                    f"{action} employee",
                )

        st.divider()
        with st.expander("Soft Delete Employee", expanded=False):
            st.warning(
                "Soft deletion disables login and hides the employee from normal "
                "management lists. Tickets, audit history, and the email record "
                "remain in PostgreSQL. This does not erase personal data."
            )
            with st.form(f"soft_delete_employee_{selected}"):
                deletion_reason = st.text_area("Reason for soft deletion")
                email_confirmation = st.text_input(
                    "Type the employee email to confirm",
                    placeholder=employee["email"],
                )
                deletion_confirm = st.checkbox(
                    "I understand this employee will lose access and be hidden"
                )
                delete_submitted = st.form_submit_button("Soft Delete Employee")
            if delete_submitted:
                if email_confirmation.strip().lower() != employee["email"].lower():
                    st.error("Email confirmation does not match the selected employee.")
                elif not deletion_confirm:
                    st.warning("Confirm the soft deletion first.")
                elif len(deletion_reason.strip()) < 5:
                    st.warning("Provide a reason of at least 5 characters.")
                else:
                    safe_action(
                        lambda: soft_delete_employee(
                            actor_user_id=user["id"], employee_user_id=selected,
                            reason=deletion_reason.strip(),
                        ),
                        "Soft delete employee",
                    )

        with st.expander("Account action history"):
            history = get_employee_account_history(
                actor_user_id=user["id"], employee_user_id=selected
            )
            if history:
                st.dataframe(history, hide_index=True, use_container_width=True)
            else:
                st.info("No previous account actions.")
    except Exception as exc:
        report_error(exc, "Employee Management")


def diagnostics_page(user):
    require_it_staff()
    st.title("Workflow Diagnostics")
    st.warning("Diagnostics do not repair missing LangGraph checkpoints. "
               "Human Review uses the separate support workflow.")
    ticket_id = st.text_input("Ticket ID")
    if st.button("Run Diagnostics"):
        if not ticket_id.strip():
            st.warning("Enter a ticket ID.")
        else:
            try:
                result = reconcile_ticket(ticket_id=ticket_id.strip(), dry_run=True)
                st.json(result)
            except Exception as exc:
                report_error(exc, "Diagnostics")


def main():
    try:
        initialize()
    except Exception as exc:
        report_error(exc, "Database initialization")
        st.stop()

    user = current_user()
    if user is None:
        render_login_page()
        return

    render_account_sidebar()
    role = user["role"]
    if role == "employee":
        pages = EMPLOYEE_PAGES
    elif role in {"it_support", "it_admin"}:
        pages = STAFF_PAGES + (ADMIN_PAGES if role == "it_admin" else [])
    else:
        st.error("Invalid account role.")
        st.stop()

    with st.sidebar:
        st.divider()
        page = st.radio("Navigation", pages, key="workspace_page_v2")
        st.caption("LangGraph · RAG · PostgreSQL")

    routes = {
        "Submit Ticket": employee_submit_page,
        "My Tickets": employee_tickets_page,
        "Overview": overview_page,
        "Ticket Management": ticket_management_page,
        "Escalation Center": escalation_page,
        "Human Review": human_review_page,
        "Employee Management": employee_management_page,
        "Workflow Diagnostics": diagnostics_page,
    }
    routes[page](user)


if __name__ == "__main__":
    main()
