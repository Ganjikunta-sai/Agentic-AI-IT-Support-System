
from src.utils.error_handler import (
    handle_error,
    log_info,
    log_warning,
    log_error
)

log_info("IT Support System started.")

log_warning("Testing warning message.")

try:
    result = 10 / 0

except Exception as error:
    error_details = handle_error(
        error,
        context="Division Test"
    )

    print("\nError Details:")
    print(error_details)

log_error("Testing error logging.")
