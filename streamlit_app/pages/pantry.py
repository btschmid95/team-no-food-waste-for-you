import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session
from services.pantry_manager import PantryManager
from services.product_manager import ProductManager
from database.tables import Ingredient
from visuals.treemap_favorite_foods import plot_consumption_treemap


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
        abs_delta = abs(delta)
        days = abs_delta.days
        hours = abs_delta.seconds // 3600
        if days >0:
            return f"EXP: {days} days"
        if days == 0:
            return f"EXP: {hours} hour(s) ago"
        
    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if days >= 365:
        years = days // 365
        return f"{years} year" if years == 1 else f"{years} years"
    if days >= 30:
        months = days // 30
        return f"{months} month" if months == 1 else f"{months} months"
    if days >= 7:
        weeks = days // 7
        return f"{weeks} week" if weeks == 1 else f"{weeks} weeks"
    if days >= 1:
        return f"{days} Day(s) {hours} Hour(s)"
    if hours >= 1:
        return f"{hours} Hour(s) {minutes} min(s)"
    return f"{minutes} min(s)"



apply_base_config()
render_sidebar()
session = get_session()
pm = PantryManager(session)
pm_products = ProductManager(session)

header_col1, header_col2 = st.columns([10, 4])

with header_col1:
    st.title("Pantry Dashboard")

with st.sidebar.expander("Pantry Buttons"):


    if st.button("❌ Clear Pantry", key="btn_clear_all"):
        st.session_state["confirm_clear_all"] = True
        st.session_state.planned_recipes = {}
        st.session_state.virtual_pantry = {}
        st.success("Pantry and planning queue have been fully cleared.")
        st.rerun()

    if st.button("🗑 Trash Pantry", key="btn_trash_all"):
        st.session_state["confirm_trash_all"] = True
        st.session_state.planned_recipes = {}
        st.session_state.virtual_pantry = {}
        st.success("Pantry and planning queue have been fully cleared.")
        st.rerun()

    if st.button("⏳ Trash Expired", key="btn_trash_expired"):
        st.session_state["confirm_trash_expired"] = True
    if st.button("🌱 Sample Pantry", key="btn_sample_pantry"):
        st.session_state["confirm_sample_pantry"] = True

    if st.session_state.get("confirm_clear_all"):
        st.error("⚠ This will permanently delete ALL pantry items AND ALL planned recipes.")
        cA, cB = st.columns(2)
        with cA:
            if st.button("Yes, Clear Everything", key="yes_clear_all"):
                msgs = pm.clear_pantry()
                st.success("Pantry has been completely cleared.")
                st.session_state["confirm_clear_all"] = False
                st.rerun()
        with cB:
            if st.button("Cancel", key="cancel_clear_all"):
                st.session_state["confirm_clear_all"] = False


    if st.session_state.get("confirm_trash_all"):
        st.warning("⚠ This will trash ALL items in the pantry (logged as waste).")
        cA, cB = st.columns(2)
        with cA:
            if st.button("Yes, Trash Pantry", key="yes_trash_all"):
                msgs = pm.trash_pantry(category=None)
                st.success("All pantry items have been trashed.")
                st.session_state["confirm_trash_all"] = False
                st.rerun()
        with cB:
            if st.button("Cancel", key="cancel_trash_all"):
                st.session_state["confirm_trash_all"] = False

    if st.session_state.get("confirm_trash_expired"):
        st.warning("⚠ This will remove ONLY expired items and log them as waste.")
        cA, cB = st.columns(2)
        with cA:
            if st.button("Yes, Remove Expired Items", key="yes_trash_expired"):
                msgs = pm.trash_expired_items()
                st.success("Expired items have been removed.")
                st.session_state["confirm_trash_expired"] = False
                st.rerun()
        with cB:
            if st.button("Cancel", key="cancel_trash_expired"):
                st.session_state["confirm_trash_expired"] = False
                
    if st.session_state.get("confirm_sample_pantry"):
        st.info("This will generate a demo pantry with items from several categories.")
        cA, cB = st.columns(2)

        with cA:
            if st.button("Yes, Generate", key="yes_sample_pantry"):
                msgs = pm.generate_sample_pantry()

                st.success("Sample pantry generated successfully!")

                for m in msgs:
                    st.write(f"• {m}")

                st.session_state["confirm_sample_pantry"] = False
                st.rerun()

        with cB:
            if st.button("Cancel", key="cancel_sample_pantry"):
                st.session_state["confirm_sample_pantry"] = False



st.markdown("---")
pantry_items = pm.get_pantry_items()
if not pantry_items.empty:
    pantry_items["date_added"] = pd.to_datetime(pantry_items["date_added"])
    pantry_items["expiration_date"] = pd.to_datetime(pantry_items["expiration_date"])

products = pm_products.get_valid_products_for_pantry()

col1, col2, col3 = st.columns([2, 2, 1.4])

with col1:
    st.subheader("Pantry Overview")

    if pantry_items.empty:
        st.info("Your pantry is empty.")
    else:
        all_categories = sorted(pantry_items["category"].dropna().unique().tolist())
        selected_categories = st.multiselect(
            "Filter by Category",
            options=all_categories,
            default=all_categories
        )

        filtered_df = pantry_items[
            pantry_items["category"].isin(selected_categories)
        ].copy()

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


import altair as alt

with col2:
    st.subheader("📊 Category Insights")

    if pantry_items.empty:
        st.info("No data to visualize.")
    else:

        df = filtered_df.copy()
        df["days_left"] = (df["expiration_date"] - datetime.now()).dt.days.clip(lower=0)

        df_all = df
        df_1d = df[df["days_left"] <= 1]
        df_7d = df[df["days_left"] <= 7]

        categories = sorted(df["category"].dropna().unique().tolist())
        chart_mode = st.radio(
            "Chart Mode",
            ["Category Totals", "Product-Level Stacked View"],
            horizontal=True
        )

        def shorten(cat):
            return cat if len(cat) <= 12 else cat[:11] + "…"

        short_map = {c: shorten(c) for c in categories}

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

        def render_product_stacked(dfx, title):

            chart_df = dfx.copy()
            chart_df["cat_short"] = chart_df["category"].map(short_map)
            chart_df = chart_df.sort_values(["category", "days_left", "product_name"])

            chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X("cat_short:N", title="Category", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("amount:Q", stack="zero", title="Total Amount"),
                    color=alt.Color(
                        "product_name:N",
                        legend=None
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

        if chart_mode == "Category Totals":
            render_category_totals(df_all, "Total Amount by Category")
            render_category_totals(df_1d, "Expiring in Next 1 Day")
            render_category_totals(df_7d, "Expiring in Next 7 Days")
        else:
            render_product_stacked(df_all, "Stacked: All Pantry Items")
            render_product_stacked(df_1d, "Stacked: Expiring in Next 1 Day")
            render_product_stacked(df_7d, "Stacked: Expiring in Next 7 Days")

        st.markdown("---")

with col3:
    st.subheader("🛒 Add Items")

    categories = sorted({p.category for p in products if p.category})
    categories.insert(0, "All")

    selected_category = st.selectbox("Category Filter", categories)
    search_text = st.text_input("Search products...", "").lower().strip()


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
        msg = pm.remove_item(pid)

        removed_ids = []
        for sel_id, pdata in list(st.session_state.planned_recipes.items()):
            rid = pdata["recipe_id"]

            ingredients = session.query(Ingredient).filter(Ingredient.recipe_id == rid).all()
            for ing in ingredients:
                if ing.matched_product_id == pantry_items.loc[
                    pantry_items["pantry_id"] == pid, "product_id"
                ].values[0]:
                    removed_ids.append(sel_id)
                    del st.session_state.planned_recipes[sel_id]
                    break

        if removed_ids:
            st.info(f"Removed {len(removed_ids)} planned recipe(s) because they needed this item.")

        st.session_state.virtual_pantry = {}
        st.rerun()

    if st.button("Trash"):
        msg = pm.trash_item(pid)

        trashed_product_id = pantry_items.loc[
            pantry_items["pantry_id"] == pid, "product_id"
        ].values[0]

        removed_ids = []
        for sel_id, pdata in list(st.session_state.planned_recipes.items()):
            rid = pdata["recipe_id"]

            ingredients = session.query(Ingredient).filter(
                Ingredient.recipe_id == rid
            ).all()

            for ing in ingredients:
                if ing.matched_product_id == trashed_product_id:
                    removed_ids.append(sel_id)
                    del st.session_state.planned_recipes[sel_id]
                    break

        if removed_ids:
            st.info(f"{msg} Also removed {len(removed_ids)} planned recipe(s).")
        else:
            st.success(msg)

        st.session_state.virtual_pantry = {}
        st.rerun()

st.markdown("## Pantry Insights")

if pantry_items.empty:
    st.info("No insights available — your pantry is empty.")
else:
    st.subheader("Pantry Roll-Up (Totals Per Item)")

    rollup_df = (
        pantry_items.groupby("product_name")["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )

    st.dataframe(rollup_df, hide_index=True, height=250)
    st.subheader("Items Expiring Soon")

    exp_df = pantry_items.copy()
    exp_df["days_left"] = (exp_df["expiration_date"] - datetime.now()).dt.days
    exp_df = exp_df.sort_values("days_left").head(10)

    st.dataframe(
        exp_df[["product_name", "amount", "unit", "days_left", "expiration_date"]],
        hide_index=True,
        height=300
    )


fig = plot_consumption_treemap(session.bind)

st.subheader("🥗 Consumption by Category & Product")
if fig:
    st.plotly_chart(fig, use_container_width=False)
else:
    st.info("No consumption data available yet!")

