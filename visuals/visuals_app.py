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
    compute_waste_summary_from_pantry,
    plot_waste_waterfall,
)
from visuals.recipe_ingredient_overlap import (
    load_recipe_ingredient_data,
    build_recipe_ingredient_graph,
    plot_recipe_overlap_network,
)


# DB connection + cached data
@st.cache_resource
### UPDATE! WHERE IS COOKBOOK????
def get_engine():
    return create_engine("sqlite:///cookbook.db")


@st.cache_data
def get_pantry_df():
    engine = get_engine()
    return load_pantry_with_category(engine)


@st.cache_data
def get_recipe_data():
    engine = get_engine()
    return load_recipe_ingredient_data(engine)


# Streamlit layout
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

    if pantry_df.empty:
        st.info("No pantry data available.")
    else:
        waste_summary = compute_waste_summary_from_pantry(pantry_df)
        if waste_summary.empty:
            st.info("No realized waste found yet.")
        else:
            fig = plot_waste_waterfall(waste_summary)
            st.pyplot(fig)


# VISUAL 4
else:
    st.subheader("Visual 4 – Recipe–Ingredient Overlap")

    recipes_df, ingredients_df, inv_idx_df = get_recipe_data()

    if recipes_df.empty or ingredients_df.empty or inv_idx_df.empty:
        st.info("Recipe or ingredient data is missing.")
    else:
        G = build_recipe_ingredient_graph(recipes_df, ingredients_df, inv_idx_df)

        #  Slider to control how many recipes are shown
        sample_n = st.slider(
            "Number of recipes to show in the network",
            min_value=10,
            max_value=100,
            value=30,
            step=5,
        )

        fig = plot_recipe_overlap_network(G, sample_n_recipes=sample_n)
        st.pyplot(fig)