import pandas as pd
import numpy as np
from datetime import datetime


def compute_waste_summary_from_events(engine):
    """
    Compute realized and avoided waste by category using PantryEvent + Pantry + TJInventory.

    realized_waste = sum(amount where event_type='trash')
    avoided_waste  = sum(amount where event_type='avoid')
    """

    events = pd.read_sql(
        """
        SELECT 
            pe.id,
            pe.timestamp,
            pe.amount,
            pe.unit,
            pe.event_type,
            pe.pantry_id,
            p.product_id,
            COALESCE(ti.category, 'Uncategorized') AS category
        FROM pantry_event pe
        -- LEFT JOIN so events still count even if the pantry row was deleted
        LEFT JOIN pantry p ON pe.pantry_id = p.pantry_id
        LEFT JOIN tj_inventory ti ON p.product_id = ti.product_id
        """,
        engine,
    )

    if events.empty:
        return pd.DataFrame(
            {
                "category": [],
                "realized_waste": [],
                "avoided_waste": [],
            }
        )

    # Make sure amount is numeric
    events["amount"] = pd.to_numeric(events["amount"], errors="coerce")
    events = events[events["amount"].notna()]

    wasted = (
        events[events["event_type"] == "trash"]
        .groupby("category", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "realized_waste"})
    )

    avoided = (
        events[events["event_type"] == "avoid"]
        .groupby("category", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "avoided_waste"})
    )

    summary = pd.merge(wasted, avoided, on="category", how="outer")
    summary = summary.fillna({"realized_waste": 0.0, "avoided_waste": 0.0})
    summary = summary.sort_values("realized_waste", ascending=False)

    return summary


def get_forecast_waste_by_date(pantry_df):
    """
    From pantry_df, compute how much is expiring each day.
    Uses pantry.amount and pantry.expiration_date.
    """
    df = pantry_df.copy()

    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
    df = df[df["expiration_date"].notna()]

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df[df["amount"].notna()]

    daily = (
        df.groupby("expiration_date", as_index=False)["amount"]
          .sum()
          .rename(columns={"expiration_date": "date", "amount": "forecast_waste"})
    )
    return daily


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
    Add days_to_expiry and expiry_bucket columns to pantry_df.

    Buckets:
      - "Expired"
      - "0–1 day"
      - "2–3 days"
      - "4–7 days"
      - "8–14 days"
      - "15–30 days"
      - "30+ days"
    """
    df = pantry_df.copy()

    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
    df = df[df["expiration_date"].notna()]

    if today is None:
        today = pd.Timestamp(datetime.today().date())

    df["days_to_expiry"] = (df["expiration_date"] - today).dt.days

    # Expired (<= 0 days)
    df["expiry_bucket"] = None
    expired_mask = df["days_to_expiry"] <= 0
    df.loc[expired_mask, "expiry_bucket"] = "Expired"

    # Positive days → bucket with pd.cut
    non_expired = df["days_to_expiry"] > 0
    bins = [0, 1, 3, 7, 14, 30, np.inf]
    labels = ["0–1 day", "2–3 days", "4–7 days", "8–14 days", "15–30 days", "30+ days"]

    df.loc[non_expired, "expiry_bucket"] = pd.cut(
        df.loc[non_expired, "days_to_expiry"],
        bins=bins,
        labels=labels,
        right=True,
        include_lowest=False,
    )

    return df


def load_recipe_product_data(engine):
    """
    Load recipe → ingredient → product mappings using the current schema.

    Uses:
      - recipe
      - ingredient (with matched_product_id)
      - tj_inventory
    Only includes ingredients that have a matched_product_id.
    """
    recipes = pd.read_sql(
        """
        SELECT recipe_id, title, category
        FROM recipe;
        """,
        engine,
    )

    ing = pd.read_sql(
        """
        SELECT ingredient_id, recipe_id, matched_product_id
        FROM ingredient
        WHERE matched_product_id IS NOT NULL;
        """,
        engine,
    )

    products = pd.read_sql(
        """
        SELECT product_id, name, category, sub_category
        FROM tj_inventory;
        """,
        engine,
    )

    return recipes, products, ing


def compute_consumption_by_category(engine):
    """
    Returns a dataframe with:
      category, product_name, total_consumed, unit

    Uses PantryEvent + Pantry + TJInventory for event_type='consume'.
    """

    q = """
        SELECT 
            COALESCE(ti.category, 'Uncategorized') AS category,
            ti.name AS product_name,
            ti.unit,
            pe.amount,
            pe.event_type
        FROM pantry_event pe
        LEFT JOIN pantry p ON pe.pantry_id = p.pantry_id
        LEFT JOIN tj_inventory ti ON p.product_id = ti.product_id
        WHERE pe.event_type = 'consume'
    """

    df = pd.read_sql(q, engine)

    if df.empty:
        return pd.DataFrame(columns=["category", "product_name", "unit", "total_consumed"])

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df[df["amount"].notna()]

    grouped = (
        df.groupby(["category", "product_name", "unit"], as_index=False)["amount"]
          .sum()
          .rename(columns={"amount": "total_consumed"})
    )

    grouped["category"] = grouped["category"].fillna("Unknown").str.strip()

    return grouped


def create_treemap_dataframe(consumption_df):
    """
    Prepare a dataframe suitable for treemap plotting libraries.
    """
    if consumption_df.empty:
        return pd.DataFrame(
            columns=["ROOT", "All Food", "category", "product", "value", "unit"]
        )

    df = consumption_df.copy()

    treemap_df = pd.DataFrame(
        {
            "ROOT": ["All Food"] * len(df),
            "All Food": df["category"],
            "category": df["category"],
            "product": df["product_name"],
            "unit": df["unit"],
            "value": df["total_consumed"],
        }
    )

    return treemap_df

def get_planned_consumption_by_date(engine):
    """
    Compute planned consumption by date based on recipe selections.

    Uses:
      - recipe_selected.planned_for (date recipes are planned)
      - ingredient.amount for each recipe

    Returns a DataFrame with columns:
      - date
      - planned_consumption
    """

    q = """
        SELECT
            DATE(rs.planned_for) AS date,
            SUM(i.amount)       AS planned_consumption
        FROM recipe_selected rs
        JOIN ingredient i
            ON rs.recipe_id = i.recipe_id
        WHERE rs.planned_for IS NOT NULL
        GROUP BY DATE(rs.planned_for)
        ORDER BY DATE(rs.planned_for)
    """

    df = pd.read_sql(q, engine)

    if df.empty:
        return pd.DataFrame(columns=["date", "planned_consumption"])

    # Ensure proper types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["planned_consumption"] = pd.to_numeric(df["planned_consumption"], errors="coerce").fillna(0)

    return df