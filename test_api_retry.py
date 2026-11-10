
from unittest.mock import patch

from groq import APIConnectionError

from src.utils.api_retry import retry_groq_api


# ==========================================
# TEST 1: TEMPORARY FAILURE THEN SUCCESS
# ==========================================

def test_retry_success():

    attempts = {"count": 0}

    @retry_groq_api(
        max_attempts=3,
        initial_delay=0
    )
    def fake_api_call():

        attempts["count"] += 1

        if attempts["count"] < 3:
            raise APIConnectionError(
                request=None
            )

        return "Classification successful"

    with patch(
        "src.utils.api_retry.time.sleep",
        return_value=None
    ):

        result = fake_api_call()

    assert attempts["count"] == 3
    assert result == "Classification successful"

    print("\nTEST 1 PASSED")
    print("Attempts:", attempts["count"])
    print("Result:", result)


# ==========================================
# TEST 2: ALL RETRIES FAIL
# ==========================================

def test_retry_failure():

    attempts = {"count": 0}

    @retry_groq_api(
        max_attempts=3,
        initial_delay=0
    )
    def fake_api_call():

        attempts["count"] += 1

        raise APIConnectionError(
            request=None
        )

    with patch(
        "src.utils.api_retry.time.sleep",
        return_value=None
    ):

        try:

            fake_api_call()

        except APIConnectionError:

            assert attempts["count"] == 3

            print("\nTEST 2 PASSED")
            print("Attempts:", attempts["count"])
            print("Error propagated after final attempt")

        else:

            raise AssertionError(
                "Expected APIConnectionError"
            )


# ==========================================
# TEST 3: PERMANENT ERROR
# ==========================================

def test_permanent_error():

    attempts = {"count": 0}

    @retry_groq_api(
        max_attempts=3,
        initial_delay=0
    )
    def fake_api_call():

        attempts["count"] += 1

        raise ValueError(
            "Invalid request"
        )

    try:

        fake_api_call()

    except ValueError:

        assert attempts["count"] == 1

        print("\nTEST 3 PASSED")
        print("Attempts:", attempts["count"])
        print("Permanent error was not retried")

    else:

        raise AssertionError(
            "Expected ValueError"
        )


# ==========================================
# RUN TESTS
# ==========================================

if __name__ == "__main__":

    print("\nGROQ API RETRY TESTS")
    print("====================")

    test_retry_success()
    test_retry_failure()
    test_permanent_error()

    print("\n====================")
    print("ALL RETRY TESTS PASSED")
