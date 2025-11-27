import streamlit as st
from sqlalchemy import create_engine

from visuals.waste_prod_vs_time import (
    load_pantry_with_category,
    plot_expiring_food_histogram,
)
from visuals.consumption_vs_waste import (
    plot_consumption_vs_waste,
)
from visuals.waste_gen_vs_saved import (
    plot_waste_waterfall,   # now works off PantryEvent + TJInventory
)
from visuals.recipe_ingredient_overlap import (
    load_recipe_product_data,    # updated to use Recipe + Ingredient + TJInventory
    build_recipe_ingredient_graph,
    plot_recipe_overlap_network,
)


# ----------------------------
# DB connection + cached data
# ----------------------------
@st.cache_resource
def get_engine():
    # NOTE: 'cookbook.db' is the SQLite DATABASE FILE, not a table name.
    # All tables (recipe, ingredient, pantry, tj_inventory, pantry_event, etc.)
    # live inside this single file.
    return create_engine("sqlite:///cookbook.db")


@st.cache_data
def get_pantry_df():
    engine = get_engine()
    return load_pantry_with_category(engine)


@st.cache_data
def get_recipe_data():
    """
    Uses the new Ingredient-based schema:
      - recipe
      - ingredient
      - tj_inventory
      - (plus any mapping logic inside load_recipe_product_data)
    """
    engine = get_engine()
    return load_recipe_product_data(engine)


# ----------------------------
# Streamlit layout
# ----------------------------
st.set_page_config(page_title="Pantry Planner Dashboard", layout="wide")

st.title("Pantry Planner Dashboard")

view = st.sidebar.radio(
    "Choose a visual:",
    [
        "Visual 1 – Expiring Food Over Time",
        "Visual 2 – Consumption vs Waste",
        "Visual 3 – Waste Generated vs Saved",
        "Visual 4 – Recipe–Ingredient Overlap",
    ],
)

engine = get_engine()
pantry_df = get_pantry_df()

# VISUAL 1
if view.startswith("Visual 1"):
    st.subheader("Visual 1 – Expiring Food Over Time")

    if pantry_df.empty:
        st.info("No pantry data available.")
    else:
        fig = plot_expiring_food_histogram(pantry_df)
        st.pyplot(fig)


# VISUAL 2
elif view.startswith("Visual 2"):
    st.subheader("Visual 2 – Consumption vs Waste")

    if pantry_df.empty:
        st.info("No pantry data available.")
    else:
        fig = plot_consumption_vs_waste(pantry_df, engine)
        st.pyplot(fig)


# VISUAL 3
elif view.startswith("Visual 3"):
    st.subheader("Visual 3 – Waste Generated vs Saved")

    # plot_waste_waterfall(engine) internally calls compute_waste_summary_from_events(engine)
    # and handles the "no data" case (shows "No waste data available.")
    fig = plot_waste_waterfall(engine)
    st.pyplot(fig)


# VISUAL 4
else:
    st.subheader("Visual 4 – Recipe–Ingredient Overlap")

    # New schema: recipes, products, and recipe→ingredient→product mapping
    recipes_df, products_df, recipe_ing_map = get_recipe_data()

    if recipes_df.empty or recipe_ing_map.empty:
        st.info("Recipe or ingredient/product mapping data is missing.")
    else:
        # build_recipe_ingredient_graph should now accept:
        #   (recipes_df, products_df, recipe_ing_map)
        G = build_recipe_ingredient_graph(recipes_df, products_df, recipe_ing_map)

        sample_n = st.slider(
            "Number of recipes to show in the network",
            min_value=10,
            max_value=100,
            value=30,
            step=5,
        )

        fig = plot_recipe_overlap_network(G, sample_n_recipes=sample_n)
        st.pyplot(fig)