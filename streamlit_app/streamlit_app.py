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

col1, col2 = st.columns(2)
col1.metric("Total Pantry Items", total_items)
col2.metric("Recipes Planned", planned_recipes)

# ============================================================
# Meal Planner KPIs
# ============================================================
st.markdown("## 🍽️ Meal Planner Insights")

# Next Meal
next_meal = (
    session.query(RecipeSelected)
    .filter(RecipeSelected.planned_for.isnot(None))
    .order_by(RecipeSelected.planned_for.asc())
    .first()
)

colA, colB = st.columns(2)

if next_meal:
    next_recipe = session.query(Recipe).filter_by(recipe_id=next_meal.recipe_id).first()
    colA.metric(
        "Next Meal Planned",
        next_recipe.title if next_recipe else "Unknown",
        next_meal.planned_for.strftime("%b %d, %Y")
    )
else:
    colA.metric("Next Meal Planned", "None", "—")

# Meals planned this week
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

colB.metric("Meals Planned This Week", weekly_count)

# ============================================================
# Analytics Section
# ============================================================
st.markdown("## 📊 Waste & Pantry Analytics")

# --- Visual 1: Expiring Food Forecast ---
st.markdown("### 🥫 Expiring Food Forecast")
fig1 = plot_expiring_food_histogram(engine)
st.pyplot(fig1)
st.markdown("---")

# --- Visual 2: Consumption vs Waste ---
st.markdown("### 🔄 Consumption vs Waste Over Time")
fig2 = plot_consumption_vs_waste(engine, recipe_mgr)
st.pyplot(fig2)
st.markdown("---")

# --- Visual 3: Realized vs Avoided Waste ---
st.markdown("### 🚯 Realized vs Avoided Waste")
fig3 = plot_waste_waterfall(engine)
st.pyplot(fig3)
st.markdown("---")

# --- Visual 4: Recipe–Product Overlap Network ---
st.markdown("### 🥗 Recipe–Product Overlap Network")

recipes_df, products_df, recipe_ing_map = load_recipe_product_data(engine)
G = build_recipe_product_graph(recipes_df, products_df, recipe_ing_map)

fig4 = plot_recipe_overlap_network(G, sample_n_recipes=30)
st.pyplot(fig4)
