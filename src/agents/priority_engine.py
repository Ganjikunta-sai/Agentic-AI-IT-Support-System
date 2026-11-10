
from typing import Literal
from pydantic import BaseModel, Field


# Define the priority output structure
class PriorityResult(BaseModel):

    priority: Literal[
        "Critical",
        "High",
        "Medium",
        "Low"
    ]

    reason: str = Field(
        description="Explanation for the assigned priority"
    )


# Priority assignment function
def assign_priority(impact, urgency):

    impact = impact.strip().capitalize()
    urgency = urgency.strip().capitalize()

    priority_rules = {

        ("High", "High"): "Critical",
        ("High", "Medium"): "High",
        ("High", "Low"): "High",

        ("Medium", "High"): "High",
        ("Medium", "Medium"): "Medium",
        ("Medium", "Low"): "Medium",

        ("Low", "High"): "Medium",
        ("Low", "Medium"): "Low",
        ("Low", "Low"): "Low"
    }

    if impact not in ["High", "Medium", "Low"]:
        raise ValueError("Invalid impact value")

    if urgency not in ["High", "Medium", "Low"]:
        raise ValueError("Invalid urgency value")

    priority = priority_rules[(impact, urgency)]

    reason = (
        f"Priority is {priority} because impact is "
        f"{impact} and urgency is {urgency}."
    )

    return PriorityResult(
        priority=priority,
        reason=reason
    )


# Test the priority engine
if __name__ == "__main__":

    test_cases = [

        ("High", "High"),
        ("High", "Medium"),
        ("Medium", "High"),
        ("Medium", "Medium"),
        ("Low", "Low")
    ]

    for impact, urgency in test_cases:

        result = assign_priority(
            impact,
            urgency
        )

        print("\nImpact:", impact)
        print("Urgency:", urgency)
        print("Priority:", result.priority)
        print("Reason:", result.reason)
