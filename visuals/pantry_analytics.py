import pandas as pd
from datetime import datetime

def compute_waste_summary_from_events(engine):
    """
    Compute realized waste by category using PantryEvent + PantryItem + TJInventory.

    Realized waste = sum of PantryEvent.amount where event_type='trash'
    Category comes from TJInventory.
    """

    # Load events
    events = pd.read_sql("""
        SELECT 
            pe.id,
            pe.timestamp,
            pe.amount,
            pe.unit,
            pe.event_type,
            p.pantry_id,
            p.product_id,
            ti.category
        FROM pantry_event pe
        JOIN pantry p ON pe.pantry_id = p.pantry_id
        JOIN tj_inventory ti ON p.product_id = ti.product_id
    """, engine)

    # Filter only waste events
    wasted = events[events["event_type"] == "trash"]

    # Aggregate waste by category
    if wasted.empty:
        return pd.DataFrame({
            "category": [],
            "realized_waste": []
        })

    summary = (
        wasted.groupby("category", as_index=False)["amount"]
              .sum()
              .rename(columns={"amount": "realized_waste"})
    )

    summary["avoided_waste"] = 0.0

    return summary

def load_pantry_with_category(engine):
    """
    Query pantry + TJInventory categories for analytics.
    """
    query = """
    SELECT
        p.pantry_id,
        p.product_id,
        p.amount,
        p.unit,
        p.date_added,
        p.expiration_date,
        ti.category
    FROM pantry p
    LEFT JOIN tj_inventory ti
        ON p.product_id = ti.product_id;
    """
    return pd.read_sql(query, engine)

def compute_expiry_buckets(pantry_df, today=None):
    """
    Add days_to_expiry and expiry_bucket columns.
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

    df["expiry_bucket"] = pd.cut(df["days_to_expiry"], bins=bins, labels=labels)

    return df

