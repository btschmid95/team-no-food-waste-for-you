from recommender_system import recipe_recommender
print("📌 Loaded file:", recipe_recommender.__file__)

import streamlit as st
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session
from datetime import datetime, timedelta
from pathlib import Path
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))
#from recommender_system.recipe_recommender import *
from services.pantry_manager import PantryManager

apply_base_config()
render_sidebar()

# ======================================================
# PAGE HEADER
# ======================================================
col_header = st.columns([7, 1])
with col_header[0]:
    st.title("📅 Planning Dashboard")
    st.caption("Plan meals, reduce waste, and optimize your pantry.")

with col_header[1]:
    refresh_clicked = st.button("🔄 Refresh")


# ======================================================
# INITIALIZE SERVICES + SESSION STATE
# ======================================================
session = get_session()
pm = PantryManager(session)
recommender = RecipeRecommender(session)

if "planned_recipes" not in st.session_state:
    st.session_state.planned_recipes = []          # list of recipe_id
if "virtual_pantry" not in st.session_state:
    st.session_state.virtual_pantry = pm.export_state()  # pantry snapshot



# ======================================================
# HANDLE PLANNING SELECTION
# ======================================================
def add_recipe_to_planner(recipe_id: int):
    if recipe_id not in st.session_state.planned_recipes:
        st.session_state.planned_recipes.append(recipe_id)
        # simulate consumption in the virtual pantry
        st.session_state.virtual_pantry = pm.simulate_recipe_use(
            recipe_id,
            st.session_state.virtual_pantry
        )
        st.success("Recipe added to planning queue!")


# ======================================================
# FILTER CONTROLS
# ======================================================
st.subheader("🔎 Recommendation Filters")

cols = st.columns([2, 2, 6])
with cols[0]:
    max_missing = st.selectbox(
        "Max Missing Ingredients",
        [0, 1, 2, 3],
        index=1,
    )

with cols[1]:
    limit = st.selectbox("Show Top N", [5, 10, 15, 20], index=0)

# ======================================================
# LOAD RECOMMENDATIONS
# ======================================================
recommendations = recommender.recommend_recipes(
    limit=limit,
    max_missing=max_missing,
    virtual_pantry_state=st.session_state.virtual_pantry
)


# ======================================================
# CAROUSEL FORMAT RECOMMENDATIONS
# ======================================================
st.markdown("## ⭐ Recommended Recipes")

if not recommendations:
    st.info("No recommended recipes for the current filter.")
else:
    # Create horizontal scroll area
    carousel_container = st.container()
    with carousel_container:
        st.write(
            "<div style='display:flex; overflow-x:auto; gap:20px; padding-bottom:10px;'>",
            unsafe_allow_html=True
        )

        for rec in recommendations:
            recipe_id = rec["recipe_id"]
            is_added = recipe_id in st.session_state.planned_recipes
            bg_color = "#eaffea" if is_added else "white"
            border_color = "#4CAF50" if is_added else "#ddd"

            tile_html = f"""
            <div style="
                min-width: 300px;
                max-width: 300px;
                border: 2px solid {border_color};
                border-radius: 10px;
                padding: 15px;
                background-color: {bg_color};
                position: relative;
            ">
                <h4 style="margin-top:0;">{rec['title']}</h4>
                <p><b>Score:</b> {rec['score']:.2f}</p>
                <p><b>Matched Ingredients:</b> {rec['matched']}</p>
                <p><b>Missing Ingredients:</b> {rec['missing']}</p>
                <p><b>External Ingredients:</b> {rec['external']}</p>
            """

            if is_added:
                tile_html += """
                <span style="
                    position:absolute;
                    top:8px; right:8px;
                    background:#4CAF50;
                    color:white;
                    padding:4px 8px;
                    border-radius:5px;
                    font-size:12px;
                ">Added</span>
                """

            tile_html += "</div>"

            st.write(tile_html, unsafe_allow_html=True)

            # Add button
            if not is_added:
                if st.button("➕", key=f"add_{recipe_id}"):
                    add_recipe_to_planner(recipe_id)
                    st.rerun()

        st.write("</div>", unsafe_allow_html=True)



# ======================================================
# ALL RECIPES BROWSER
# ======================================================
st.markdown("## 📚 All Recipes")

with st.expander("Browse full recipe list"):
    search_term = st.text_input("Search recipes by name or ingredient")

    st.write("_Recipe list will load from DB soon..._")



# ======================================================
# PLANNING QUEUE
# ======================================================
st.markdown("## 📝 Your Planning Queue")

if not st.session_state.planned_recipes:
    st.warning("No recipes added to the planner yet.")
else:
    for i, rid in enumerate(st.session_state.planned_recipes):
        rec = next(r for r in recommendations if r["recipe_id"] == rid)

        with st.expander(f"{i+1}. {rec['title']}"):
            date = st.date_input(
                "Choose a cooking date:",
                datetime.now().date() + timedelta(days=i+1),
                key=f"date_picker_{rid}"
            )

            if st.button("✔️ Confirm & Lock In", key=f"confirm_{rid}"):
                # TODO: implement finalization
                st.success("Recipe confirmed! Pantry updated.")
