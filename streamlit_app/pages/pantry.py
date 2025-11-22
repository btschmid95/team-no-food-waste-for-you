import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Make repo root importable
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Project imports
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session
from services.pantry_manager import PantryManager
from services.product_manager import ProductManager
from database.tables import PantryItem, TJInventory

# Visual imports
from visuals.waste_prod_vs_time import plot_expiring_food_histogram

def format_date_added(dt: datetime) -> str:
    if pd.isna(dt):
        return ""
    return dt.strftime("%Y-%m-%d")

def format_time_remaining(expiration: datetime) -> str:
    if pd.isna(expiration):
        return ""

    now = datetime.now()
    delta = expiration - now

    if delta.total_seconds() < 0:
        return "Expired"

    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    # Years
    if days >= 365:
        years = days // 365
        return f"{years} year" if years == 1 else f"{years} years"

    # Months
    if days >= 30:
        months = days // 30
        return f"{months} month" if months == 1 else f"{months} months"

    # Weeks
    if days >= 7:
        weeks = days // 7
        return f"{weeks} week" if weeks == 1 else f"{weeks} weeks"

    # Days + hours
    if days >= 1:
        return f"{days} Day(s) {hours} Hour(s)"

    # Less than a day → hours + minutes
    if hours >= 1:
        return f"{hours} Hour(s) {minutes} min(s)"

    # Less than 1 hour → minutes countdown
    return f"{minutes} min(s)"



apply_base_config()
render_sidebar()
session = get_session()
pm = PantryManager(session)
pm_products = ProductManager(session)

st.title("🥫 Pantry Dashboard")

# Load pantry items
pantry_items = pm.get_pantry_items()
if not pantry_items.empty:
    pantry_items["date_added"] = pd.to_datetime(pantry_items["date_added"])
    pantry_items["expiration_date"] = pd.to_datetime(pantry_items["expiration_date"])

# Load valid products
products = pm_products.get_valid_products_for_pantry()


# ------------------------------------------------------
#  THREE-COLUMN LAYOUT
# ------------------------------------------------------
col1, col2, col3 = st.columns([2, 2, 1.4])

# ======================================================
# COLUMN 1 — PANTRY TABLE WITH FILTERS + SORTING
# ======================================================
with col1:
    st.subheader("📋 Pantry Overview")

    if pantry_items.empty:
        st.info("Your pantry is empty.")
    else:
        # -----------------------------------------
        # Category Filter
        # -----------------------------------------
        all_categories = sorted(pantry_items["category"].dropna().unique().tolist())
        selected_categories = st.multiselect(
            "Filter by Category",
            options=all_categories,
            default=all_categories
        )

        filtered_df = pantry_items[
            pantry_items["category"].isin(selected_categories)
        ].copy()

        # -----------------------------------------
        # Sorting Toggle
        # -----------------------------------------
        sort_mode = st.radio(
            "Sort Pantry By:",
            ["Expiration Soonest", "Expiration Latest", "Date Added (Newest)", "Date Added (Oldest)"],
            horizontal=True
        )

        if sort_mode == "Expiration Soonest":
            filtered_df = filtered_df.sort_values("expiration_date", ascending=True)
        elif sort_mode == "Expiration Latest":
            filtered_df = filtered_df.sort_values("expiration_date", ascending=False)
        elif sort_mode == "Date Added (Newest)":
            filtered_df = filtered_df.sort_values("date_added", ascending=False)
        else:
            filtered_df = filtered_df.sort_values("date_added", ascending=True)

        # -----------------------------------------
        # BEAUTIFUL DATE FORMATTING
        # -----------------------------------------
        filtered_df["date_added_fmt"] = filtered_df["date_added"].apply(format_date_added)
        filtered_df["expires_in"] = filtered_df["expiration_date"].apply(format_time_remaining)

        display_df = filtered_df[[
            "product_name",
            "amount",
            "unit",
            "date_added_fmt",
            "expires_in"
        ]].rename(columns={
            "date_added_fmt": "Date Added",
            "expires_in": "Expires In"
        })

        st.dataframe(display_df, height=600, hide_index=True)


# ======================================================
# COLUMN 2 — CATEGORY VISUAL STACK
# ======================================================
import altair as alt

with col2:
    st.subheader("📊 Category Insights")

    if pantry_items.empty:
        st.info("No data to visualize.")
        st.stop()

    # Prep dataset
    df = filtered_df.copy()
    df["days_left"] = (df["expiration_date"] - datetime.now()).dt.days.clip(lower=0)

    # Time windows
    df_all = df
    df_1d = df[df["days_left"] <= 1]
    df_7d = df[df["days_left"] <= 7]

    # Unique categories
    categories = sorted(df["category"].dropna().unique().tolist())

    # Toggle: totals or stacked product breakdown
    chart_mode = st.radio(
        "Chart Mode",
        ["Category Totals", "Product-Level Stacked View"],
        horizontal=True
    )

    # ---- Helper to shorten category labels ----
    def shorten(cat):
        return cat if len(cat) <= 12 else cat[:11] + "…"

    short_map = {c: shorten(c) for c in categories}

    # =============== MODE A: Category Totals ===============
    def render_category_totals(dfx, title):
        chart_df = (
            dfx.groupby("category")["amount"]
            .sum()
            .reindex(categories)
            .fillna(0)
            .reset_index()
        )
        chart_df["cat_short"] = chart_df["category"].map(short_map)

        chart = (
            alt.Chart(chart_df)
            .mark_bar(size=28)
            .encode(
                x=alt.X("cat_short:N", title="Category", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("amount:Q", title="Total Amount"),
                tooltip=["category", "amount"]
            )
            .properties(title=title, width="container", height=250)
        )
        st.altair_chart(chart, use_container_width=True)

    # =============== MODE B: Product-Level Stacked ===============
    def render_product_stacked(dfx, title):
        # if dfx.empty:
        #     st.info(f"No items for {title}")
        #     return

        chart_df = dfx.copy()
        chart_df["cat_short"] = chart_df["category"].map(short_map)

        # Sorting products within each category by expiration → bottom is most urgent
        chart_df = chart_df.sort_values(["category", "days_left", "product_name"])

        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("cat_short:N", title="Category", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("amount:Q", stack="zero", title="Total Amount"),
                color=alt.Color(
                    "product_name:N",
                    legend=None  # turn on if you want a legend
                ),
                tooltip=[
                    "product_name",
                    "amount",
                    "unit",
                    "expiration_date",
                    "days_left"
                ]
            )
            .properties(title=title, width="container", height=250)
        )

        st.altair_chart(chart, use_container_width=True)

    # =============== RENDER 3 CHARTS BASED ON MODE ===============
    if chart_mode == "Category Totals":
        render_category_totals(df_all, "Total Amount by Category")
        render_category_totals(df_1d, "Expiring in Next 1 Day")
        render_category_totals(df_7d, "Expiring in Next 7 Days")
    else:
        render_product_stacked(df_all, "Stacked: All Pantry Items")
        render_product_stacked(df_1d, "Stacked: Expiring in Next 1 Day")
        render_product_stacked(df_7d, "Stacked: Expiring in Next 7 Days")

    st.markdown("---")


# ======================================================
# COLUMN 3 — ADD / REMOVE ITEMS
# ======================================================
with col3:
    st.subheader("🛒 Add Items")

    # Category Filter
    categories = sorted({p.category for p in products if p.category})
    categories.insert(0, "All")

    selected_category = st.selectbox("Category Filter", categories)

    search_text = st.text_input("Search products...", "").lower().strip()

    # Apply product filters
    filtered_products = [
        p for p in products
        if (selected_category == "All" or p.category == selected_category)
        and (search_text in p.name.lower())
    ]

    if not filtered_products:
        st.warning("No matching products.")
    else:
        product_name = st.selectbox(
            "Select Product",
            options=[p.name for p in filtered_products]
        )

        prod = next(p for p in filtered_products if p.name == product_name)

        st.markdown(f"**Unit:** {prod.unit}")
        st.markdown(f"**Package Qty:** {prod.quantity}")
        st.markdown(f"**Shelf Life:** {prod.shelf_life_days} days")

        num = st.number_input("Packages to Add", min_value=1, step=1)

        if st.button("Add to Pantry"):
            for _ in range(num):
                pm.add_item(prod.product_id, prod.quantity, prod.unit)
            st.success(f"Added {num} × {prod.name}")
            st.rerun()

    st.markdown("---")
    st.subheader("🗑 Manage Items")

    if pantry_items.empty:
        st.info("No items to modify.")
    else:
        pid = st.selectbox(
            "Select Pantry Item",
            options=pantry_items["pantry_id"],
            format_func=lambda p: pantry_items.loc[
                pantry_items["pantry_id"] == p, "product_name"
            ].values[0]
        )

        if st.button("Remove"):
            pm.remove_item(pid)
            st.rerun()

        if st.button("Trash"):
            pm.remove_item(pid)
            st.rerun()


st.markdown("## 📊 Pantry Insights")

if pantry_items.empty:
    st.info("No insights available — your pantry is empty.")
    st.stop()

# ======================================================
# VISUAL 2 — Pantry Roll-Up (Total Amount per Product)
# ======================================================
st.subheader("📦 Pantry Roll-Up (Totals Per Item)")

rollup_df = (
    pantry_items.groupby("product_name")["amount"]
    .sum()
    .reset_index()
    .sort_values("amount", ascending=False)
)

st.dataframe(rollup_df, hide_index=True, height=250)

# ======================================================
# VISUAL 3 — Items Expiring Soon
# ======================================================
st.subheader("⏳ Items Expiring Soon")

exp_df = pantry_items.copy()
exp_df["days_left"] = (exp_df["expiration_date"] - datetime.now()).dt.days
exp_df = exp_df.sort_values("days_left").head(10)

st.dataframe(
    exp_df[["product_name", "amount", "unit", "days_left", "expiration_date"]],
    hide_index=True,
    height=300
)

# ======================================================
# VISUAL 4 — Expiring Food Histogram
# ======================================================
st.subheader("📉 Expiration Forecast Histogram")

# Visual 4: Expiration Histogram
from visuals.waste_prod_vs_time import plot_expiring_food_histogram

# Visual 5: Consumption vs Waste
from visuals.consumption_vs_waste import plot_consumption_vs_waste

# Visual 6: Recipe–Product Overlap Graph
from visuals.recipe_ingredient_overlap import (
    build_recipe_product_graph,
    plot_recipe_overlap_network
)

# Visual 3: Waste Waterfall (optional)
from visuals.waste_gen_vs_saved import plot_waste_waterfall

try:
    fig = plot_expiring_food_histogram(session.bind)
    st.pyplot(fig)
except Exception as e:
    st.warning(f"Histogram unavailable: {e}")

