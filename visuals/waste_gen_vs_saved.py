import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime


def compute_waste_summary_from_pantry(pantry_df, today=None):
    """
    Compute a simple waste summary by category.
    """
    if today is None:
        today = pd.Timestamp(datetime.today().date())

    df = pantry_df.copy()
    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
    df["category"] = df["category"].fillna("Unknown")

    expired = df[df["expiration_date"] < today]

    realized = (
        expired.groupby("category", as_index=False)["amount"]
               .sum()
               .rename(columns={"amount": "realized_waste"})
    )

    realized["avoided_waste"] = 0.0

    return realized


def plot_waste_waterfall(waste_summary):
    """
    Visual 3:
    Waterfall-style bar chart of realized vs avoided waste by category.
    """
    df = waste_summary.copy()
    df = df.sort_values("realized_waste", ascending=False)

    steps = []
    labels = []

    cumulative = 0

    steps.append(0)
    labels.append("Start")

    for _, row in df.iterrows():
        cat = row["category"]
        realized = row["realized_waste"]
        avoided = row["avoided_waste"]

        # negative bar = realized waste
        steps.append(-realized)
        labels.append(f"{cat} wasted")

        # positive bar = avoided waste (currently 0, but kept for future use)
        if avoided != 0:
            steps.append(avoided)
            labels.append(f"{cat} avoided")

    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(10, 5))

    prev = 0
    for i, step in enumerate(steps):
        color = "red" if step < 0 else "green"
        ax.bar(x[i], step, bottom=prev, color=color)
        prev += step

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Waste (amount units)")
    ax.set_title("Realized vs Avoided Waste by Category (Simple Approximation)")
    plt.tight_layout()
    return fig