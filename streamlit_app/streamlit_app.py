# streamlit_app.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# --- VISUALS (Your Imports Kept Exactly As-Is) ---
from visuals.waste_prod_vs_time import plot_expiring_food_histogram
from visuals.consumption_vs_waste import plot_consumption_vs_waste
from visuals.waste_gen_vs_saved import plot_waste_waterfall
from visuals.recipe_ingredient_overlap import (
    build_recipe_product_graph,
    plot_recipe_overlap_network
)

# --- SERVICES ---
from services.recipe_manager import RecipeManager
from services.pantry_manager import PantryManager

# --- DB / Session ---
from utils.session import get_session, get_engine

# Import necessary DB models
from database.tables import PantryItem, RecipeSelected, Recipe
from visuals.pantry_analytics import load_recipe_product_data

# Streamlit + Themeing
import streamlit as st
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar

# --- Page Setup ---
st.set_page_config(
    page_title="Team No Food Waste",
    page_icon="🥕",
    layout="wide",
)

apply_base_config()
render_sidebar()

# --- Database Session (cached via Streamlit) ---
session = get_session()
engine = get_engine()

recipe_mgr = RecipeManager(session)
pantry_mgr = PantryManager(session)

# --- Home Page ---
st.title("🏠 Home Dashboard")

# ============================================================
# KPIs
# ============================================================
total_items = session.query(PantryItem).count()
planned_recipes = session.query(RecipeSelected).count()

col1, col2, col3, col4 = st.columns(4)
def metric_tile(label: str, value: str, subvalue: str = ""):
    return f"""
        <div style="
            padding: 12px;
            border-radius: 10px;
            background-color: #f6f6f6;
            border: 1px solid #ddd;
            min-height: 90px;
        ">
            <div style="font-size: 0.8rem; opacity: 0.6;">
                {label}
            </div>
            <div style="font-size: 1.4rem; font-weight: 700; margin-top: 4px;">
                {value}
            </div>
            {f'<div style="font-size: 0.85rem; opacity: 0.7;">{subvalue}</div>' if subvalue else ""}
        </div>
    """

# --- Total Pantry Items ---
col1.markdown(
    metric_tile("Total Pantry Items", str(total_items)),
    unsafe_allow_html=True
)

# --- Recipes Planned ---
col2.markdown(
    metric_tile("Recipes Planned", str(planned_recipes)),
    unsafe_allow_html=True
)

# --- Next Meal Planned ---
next_meal = (
    session.query(RecipeSelected)
    .filter(RecipeSelected.planned_for.isnot(None))
    .order_by(RecipeSelected.planned_for.asc())
    .first()
)

if next_meal:
    next_recipe = session.query(Recipe).filter_by(recipe_id=next_meal.recipe_id).first()
    title = next_recipe.title if next_recipe else "Unknown"
    date = next_meal.planned_for.strftime("%b %d, %Y")
    col3.markdown(
        metric_tile("Next Meal Planned", title, date),
        unsafe_allow_html=True
    )
else:
    col3.markdown(
        metric_tile("Next Meal Planned", "No meals planned!"),
        unsafe_allow_html=True
    )

# --- Meals Planned This Week ---
from datetime import datetime, timedelta
today = datetime.now().date()
end_of_week = today + timedelta(days=7)

weekly_count = (
    session.query(RecipeSelected)
    .filter(
        RecipeSelected.planned_for >= today,
        RecipeSelected.planned_for <= end_of_week
    )
    .count()
)

col4.markdown(
    metric_tile("Meals Planned This Week", str(weekly_count)),
    unsafe_allow_html=True
)
st.markdown("## Waste & Pantry Analytics")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Expiring Food Forecast")
    fig1 = plot_expiring_food_histogram(engine)
    st.pyplot(fig1)

with col2:
    st.markdown("### Consumption vs Waste Over Time")
    fig2 = plot_consumption_vs_waste(engine, recipe_mgr)
    st.pyplot(fig2)

st.markdown("---")

col3, col4 = st.columns(2)

with col3:
    st.markdown("### Realized vs Avoided Waste")
    fig3 = plot_waste_waterfall(engine)
    st.pyplot(fig3)

with col4:
    st.markdown("### Recipe–Product Overlap Network")
    recipes_df, products_df, recipe_ing_map = load_recipe_product_data(engine)
    G = build_recipe_product_graph(recipes_df, products_df, recipe_ing_map)
    fig4 = plot_recipe_overlap_network(G, sample_n_recipes=30)
    st.pyplot(fig4)

