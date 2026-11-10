
"""Two-portal Streamlit login and employee registration UI."""

from __future__ import annotations

import streamlit as st

from src.auth.service import DuplicateEmailError, register_employee
from src.auth.session import current_user, login, logout


def _login_form(portal: str) -> None:
    """Display the appropriate login form."""

    title = (
        "Employee Login"
        if portal == "employee"
        else "IT Desk Login"
    )

    st.subheader(title)

    if portal == "it_desk":
        st.caption(
            "IT Support and IT Admin use accounts "
            "created by an administrator."
        )

    with st.form(
        f"login_form_{portal}",
        clear_on_submit=False,
    ):
        email = st.text_input(
            "Email address",
            key=f"login_email_{portal}",
        )

        password = st.text_input(
            "Password",
            type="password",
            key=f"login_password_{portal}",
        )

        submitted = st.form_submit_button(
            "Log in",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    if not email.strip() or not password:
        st.warning("Enter your email and password.")
        return

    try:
        user = login(
            email=email.strip(),
            password=password,
            portal=portal,
        )

    except Exception:
        st.error(
            "Login is temporarily unavailable. "
            "Please contact support."
        )
        return

    if user is None:
        st.error(
            "Invalid email or password, or this account "
            "cannot access this portal."
        )
        return

    st.success("Signed in successfully.")
    st.rerun()


def _employee_registration() -> None:
    """Display employee account registration."""

    st.subheader("Create an Employee Account")

    st.caption(
        "New accounts receive Employee access only. "
        "IT staff accounts are administrator-managed."
    )

    with st.form(
        "employee_registration_form",
        clear_on_submit=True,
    ):
        full_name = st.text_input(
            "Full name"
        )

        email = st.text_input(
            "Work email"
        )

        password = st.text_input(
            "Create password (8–10 characters)",
            type="password",
        )

        confirm_password = st.text_input(
            "Confirm password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Create employee account",
            use_container_width=True,
        )

    if not submitted:
        return

    if password != confirm_password:
        st.error("Passwords do not match.")
        return

    if not 8 <= len(password) <= 10:
        st.error(
            "Password must contain between "
            "8 and 10 characters."
        )
        return

    try:
        register_employee(
            full_name=full_name,
            email=email,
            password=password,
        )

    except DuplicateEmailError:
        st.error(
            "An account with this email already exists."
        )

    except (TypeError, ValueError) as exc:
        st.error(str(exc))

    except Exception:
        st.error(
            "Registration is temporarily unavailable. "
            "Please try again later."
        )

    else:
        st.success(
            "Employee account created successfully. "
            "Select Employee Login to sign in."
        )


def render_login_page() -> None:
    """Display Employee and IT Desk login portals."""

    user = current_user()

    if user is not None:
        st.info(
            f"Already signed in as "
            f"{user['full_name']} ({user['role']})."
        )

        if st.button(
            "Log out",
            key="auth_logout_from_login",
        ):
            logout()
            st.rerun()

        return

    st.title("AI IT Support & Ticket Resolution")
    st.write("Choose your portal to continue.")

    employee_tab, desk_tab = st.tabs(
        ["Employee Portal", "IT Desk Portal"]
    )

    with employee_tab:
        login_tab, register_tab = st.tabs(
            ["Log in", "Register"]
        )

        with login_tab:
            _login_form("employee")

        with register_tab:
            _employee_registration()

    with desk_tab:
        _login_form("it_desk")


def render_account_sidebar() -> None:
    """Display logged-in account information."""

    user = current_user()

    if user is None:
        return

    with st.sidebar:
        st.write(
            f"**{user['full_name']}**"
        )

        st.caption(
            f"{user['email']} · {user['role']}"
        )

        if st.button(
            "Log out",
            key="auth_sidebar_logout",
            use_container_width=True,
        ):
            logout()
            st.rerun()
