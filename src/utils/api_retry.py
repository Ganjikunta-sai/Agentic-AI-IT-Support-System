
import random
import time

from functools import wraps

from groq import (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)

from src.utils.error_handler import (
    log_info,
    log_warning,
    handle_error,
)


RETRYABLE_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)


def retry_groq_api(
    max_attempts=3,
    initial_delay=2,
    max_delay=30,
):
    """
    Retry temporary Groq API failures.

    max_attempts includes the first API call.
    Authentication and validation errors are not retried.
    """

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            for attempt in range(1, max_attempts + 1):

                try:
                    return func(*args, **kwargs)

                except RETRYABLE_ERRORS as error:

                    if attempt == max_attempts:
                        handle_error(
                            error,
                            context=f"Groq API - {func.__name__}"
                        )
                        raise

                    delay = min(
                        initial_delay * (2 ** (attempt - 1)),
                        max_delay,
                    )

                    # Small random jitter reduces synchronized retries.
                    delay += random.uniform(0, 1)

                    log_warning(
                        f"Temporary Groq API failure in "
                        f"{func.__name__}. "
                        f"Attempt {attempt}/{max_attempts}. "
                        f"Retrying in {delay:.1f} seconds."
                    )

                    time.sleep(delay)

        return wrapper

    return decorator
