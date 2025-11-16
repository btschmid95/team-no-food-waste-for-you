import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime


def load_pantry_with_category(engine):
    """
    Pull pantry + category from the DB.
    """
    query = """
    SELECT
        p.pantry_id,
        p.ingredient_id,
        p.amount,
        p.unit,
        p.date_purchased,
        p.expiration_date,
        ti.category
    FROM pantry p
    LEFT JOIN sold_as sa
        ON p.ingredient_id = sa.ingredient_id
    LEFT JOIN tj_inventory ti
        ON sa.product_id = ti.product_id;
    """
    return pd.read_sql(query, engine)

def prep_expiring_food_bins(pantry_df, today=None):
    """
    Add:
      - days_to_expiry
      - expiry_bucket
    """
    df = pantry_df.copy()
    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
    df = df[df["expiration_date"].notna()]

    if today is None:
        today = pd.Timestamp(datetime.today().date())

    df["days_to_expiry"] = (df["expiration_date"] - today).dt.days

    df = df[df["days_to_expiry"] >= 0]

    bins = [0, 1, 3, 7, 14, 30, np.inf]
    labels = ["0–1 day", "2–3 days", "4–7 days", "8–14 days", "15–30 days", "30+ days"]

    df["expiry_bucket"] = pd.cut(df["days_to_expiry"], bins=bins, labels=labels, right=True)

    return df

def plot_expiring_food_histogram(pantry_df):
    """
    Visual 1: Stacked Histogram
    Variables: Waste, Product x. Time
    """
    df = prep_expiring_food_bins(pantry_df)

    df["category"] = df["category"].fillna("Unknown")

    grouped = (
        df.groupby(["expiry_bucket", "category"], observed=True)["amount"]
          .sum()
          .reset_index()
    )

    pivot = grouped.pivot(index="expiry_bucket",
                          columns="category",
                          values="amount").fillna(0)

    pivot = pivot.reindex(
        ["0–1 day", "2–3 days", "4–7 days", "8–14 days", "15–30 days", "30+ days"]
    )

    fig, ax = plt.subplots()
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_xlabel("Time Until Expiry")
    ax.set_ylabel("Total Amount")
    ax.set_title("Expiring Food Forecast")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    return fig