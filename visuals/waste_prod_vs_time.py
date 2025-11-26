import matplotlib.pyplot as plt
import sys
from pathlib import Path
import pandas as pd

# Make repo root importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Load pantry joined with TJ inventory category
try:
    from visuals.pantry_analytics import load_pantry_with_category
except ImportError:
    from pantry_analytics import load_pantry_with_category


def _bucket_expiry_days(days_to_expiry: int) -> str:
    """
    Map days until expiry into a human-readable bucket.
    """
    if pd.isna(days_to_expiry):
        return "Unknown"

    if days_to_expiry < 0:
        return "Expired"
    elif 0 <= days_to_expiry <= 3:
        return "1–3 days"
    elif 4 <= days_to_expiry <= 7:
        return "4–7 days"
    elif 8 <= days_to_expiry <= 14:
        return "8–14 days"
    elif 15 <= days_to_expiry <= 30:
        return "15–30 days"
    else:
        return "30+ days"


def plot_expiring_food_histogram(engine):
    """
    Expiring food forecast (stacked histogram).

    Uses:
      - pantry.amount (numeric, per item in pantry)
      - pantry.expiration_date (DateTime)
      - tj_inventory.category (joined via load_pantry_with_category)

    Output:
      Stacked bar chart:
        x-axis  = time-until-expiry buckets
        stacks  = product category
        height  = total amount at risk in that window
    """
    pantry_df = load_pantry_with_category(engine)

    if pantry_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "No pantry items available.\nAdd items to view forecast.",
            ha="center",
            va="center",
            fontsize=14,
        )
        ax.set_axis_off()
        return fig

    df = pantry_df.copy()

    # Ensure expiration_date is datetime
    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
    df = df[df["expiration_date"].notna()]

    # Ensure amount is numeric
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df[df["amount"].notna()]

    # Days until expiry relative to "today"
    today = pd.Timestamp.now().normalize()
    df["days_to_expiry"] = (df["expiration_date"].dt.normalize() - today).dt.days

    # Bucket by days to expiry
    df["expiry_bucket"] = df["days_to_expiry"].apply(_bucket_expiry_days)

    # Aggregate total amount per (bucket, category)
    grouped = (
        df.groupby(["expiry_bucket", "category"], observed=True)["amount"]
          .sum()
          .reset_index()
    )

    # Pivot to wide: rows = buckets, columns = categories
    pivot = (
        grouped.pivot(index="expiry_bucket", columns="category", values="amount")
        .fillna(0)
    )

    # Order buckets consistently
    bucket_order = [
        "Expired",
        "1-3 days",
        "4–7 days",
        "8–14 days",
        "15–30 days",
        "30+ days",
    ]
    pivot = pivot.reindex(bucket_order)

    # Plot stacked bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    pivot.plot(kind="bar", stacked=True, ax=ax)

    ax.set_xlabel("Time Until Expiry")
    ax.set_ylabel("Total Amount (pantry units)")
    ax.set_title("Expiring Food Forecast")
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()
    return fig