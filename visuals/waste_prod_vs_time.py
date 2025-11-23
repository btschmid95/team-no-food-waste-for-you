import matplotlib.pyplot as plt
import sys
from pathlib import Path
import pandas as pd

# Make repo root importable
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
def plot_expiring_food_histogram(engine):
    from visuals.pantry_analytics import load_pantry_with_category, compute_expiry_buckets
    pantry_df = load_pantry_with_category(engine)

    if pantry_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No pantry items available.\nAdd items to view forecast.",
                ha="center", va="center", fontsize=14)
        ax.set_axis_off()
        return fig
   
    df = compute_expiry_buckets(pantry_df)
    df["category"] = df["category"].fillna("Unknown")

    grouped = (
        df.groupby(["expiry_bucket", "category"], observed=True)["amount"]
          .sum()
          .reset_index()
    )

    pivot = grouped.pivot(index="expiry_bucket",
                          columns="category",
                          values="amount").fillna(0)

    pivot = pivot.reindex([
        "0–1 day", "2–3 days", "4–7 days",
        "8–14 days", "15–30 days", "30+ days"
    ])

    fig, ax = plt.subplots(figsize=(10, 6))
    pivot.plot(kind="bar", stacked=True, ax=ax)

    ax.set_xlabel("Time Until Expiry")
    ax.set_ylabel("Total Amount")
    ax.set_title("Expiring Food Forecast")
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()
    return fig