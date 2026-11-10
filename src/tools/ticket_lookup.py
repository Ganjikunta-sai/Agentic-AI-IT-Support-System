
import pandas as pd
import re

from pathlib import Path


# Historical ticket dataset
HISTORY_PATH = Path("data/ticket_history.csv")


def load_ticket_history():

    if not HISTORY_PATH.exists():
        raise FileNotFoundError(
            f"Ticket history file not found: {HISTORY_PATH}"
        )

    df = pd.read_csv(HISTORY_PATH)

    required_columns = {
        "ticket_id",
        "issue",
        "category",
        "resolution",
        "status"
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns in ticket history: {missing}"
        )

    return df


# Convert text into searchable words
def tokenize(text):

    return set(
        re.findall(r"\b[a-z0-9]+\b", str(text).lower())
    )


# Search previous tickets
def search_similar_tickets(
    query,
    category=None,
    limit=3
):

    df = load_ticket_history()

    # Only use resolved tickets as historical evidence
    df = df[
        df["status"].str.lower() == "resolved"
    ].copy()

    # Filter by category when provided
    if category:
        df = df[
            df["category"].str.lower() == category.lower()
        ]

    query_words = tokenize(query)

    results = []

    for _, row in df.iterrows():

        issue_words = tokenize(row["issue"])

        # Calculate keyword overlap
        common_words = query_words.intersection(
            issue_words
        )

        if not common_words:
            continue

        score = len(common_words) / max(
            len(query_words), 1
        )

        results.append({
            "ticket_id": row["ticket_id"],
            "issue": row["issue"],
            "category": row["category"],
            "resolution": row["resolution"],
            "similarity_score": round(score, 3)
        })

    # Sort by keyword overlap score
    results.sort(
        key=lambda x: x["similarity_score"],
        reverse=True
    )

    return results[:limit]


# Test the lookup tool
if __name__ == "__main__":

    employee_query = "My VPN authentication is failing"

    previous_tickets = search_similar_tickets(
        query=employee_query,
        category="Network",
        limit=3
    )

    print("\nEmployee Issue:")
    print(employee_query)

    print("\nSimilar Historical Tickets:")

    if not previous_tickets:
        print("No matching historical tickets found.")

    for ticket in previous_tickets:

        print("\n----------------------------")
        print("Ticket ID:", ticket["ticket_id"])
        print("Issue:", ticket["issue"])
        print("Category:", ticket["category"])
        print("Resolution:", ticket["resolution"])
        print("Keyword Match Score:",
              ticket["similarity_score"])
