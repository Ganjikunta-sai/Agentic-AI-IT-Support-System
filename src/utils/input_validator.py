
import re


# ==========================================
# INPUT LIMITS
# ==========================================

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 100

MIN_ISSUE_LENGTH = 10
MAX_ISSUE_LENGTH = 2000


# ==========================================
# VALIDATE EMPLOYEE NAME
# ==========================================

def validate_employee_name(name):

    if not isinstance(name, str):
        return False, "Employee name must be text."

    name = name.strip()

    if not name:
        return False, "Employee name cannot be empty."

    if len(name) < MIN_NAME_LENGTH:
        return False, "Employee name must contain at least 2 characters."

    if len(name) > MAX_NAME_LENGTH:
        return False, "Employee name cannot exceed 100 characters."

    if not re.fullmatch(r"[\w .'-]+", name, flags=re.UNICODE):
        return False, "Employee name contains invalid characters."

    return True, "Valid employee name."


# ==========================================
# VALIDATE TICKET DESCRIPTION
# ==========================================

def validate_ticket_description(issue):

    if not isinstance(issue, str):
        return False, "Ticket description must be text."

    issue = issue.strip()

    if not issue:
        return False, "Ticket description cannot be empty."

    if len(issue) < MIN_ISSUE_LENGTH:
        return False, "Please provide at least 10 characters describing the issue."

    if len(issue) > MAX_ISSUE_LENGTH:
        return False, "Ticket description cannot exceed 2000 characters."

    if not re.search(r"[a-zA-Z]", issue):
        return False, "Please describe your issue using readable text."

    return True, "Valid ticket description."


# ==========================================
# VALIDATE COMPLETE TICKET
# ==========================================

def validate_ticket(employee_name, issue):

    name_valid, name_message = validate_employee_name(
        employee_name
    )

    if not name_valid:
        return False, name_message

    issue_valid, issue_message = validate_ticket_description(
        issue
    )

    if not issue_valid:
        return False, issue_message

    return True, "Ticket input is valid."
