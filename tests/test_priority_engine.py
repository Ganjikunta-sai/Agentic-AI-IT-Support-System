
import pytest

from src.agents.priority_engine import assign_priority


# ==========================================
# TEST VALID PRIORITY COMBINATIONS
# ==========================================

@pytest.mark.parametrize(
    "impact, urgency, expected_priority",
    [
        ("High", "High", "Critical"),
        ("High", "Medium", "High"),
        ("High", "Low", "High"),
        ("Medium", "High", "High"),
        ("Medium", "Medium", "Medium"),
        ("Medium", "Low", "Medium"),
        ("Low", "High", "Medium"),
        ("Low", "Medium", "Low"),
        ("Low", "Low", "Low"),
    ]
)
def test_priority_rules(
    impact,
    urgency,
    expected_priority
):

    result = assign_priority(
        impact=impact,
        urgency=urgency
    )

    assert result.priority == expected_priority

    assert result.reason


# ==========================================
# TEST CASE INSENSITIVITY
# ==========================================

def test_lowercase_values():

    result = assign_priority(
        impact="high",
        urgency="high"
    )

    assert result.priority == "Critical"


# ==========================================
# TEST INVALID IMPACT
# ==========================================

def test_invalid_impact():

    with pytest.raises(ValueError):

        assign_priority(
            impact="Unknown",
            urgency="High"
        )


# ==========================================
# TEST INVALID URGENCY
# ==========================================

def test_invalid_urgency():

    with pytest.raises(ValueError):

        assign_priority(
            impact="High",
            urgency="Unknown"
        )


# ==========================================
# TEST PRIORITY EXPLANATION
# ==========================================

def test_priority_reason():

    result = assign_priority(
        impact="High",
        urgency="High"
    )

    assert result.priority == "Critical"

    assert "High" in result.reason

    assert "Critical" in result.reason
