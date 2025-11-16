import streamlit as st
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session
from datetime import datetime, timedelta

# ------------------------------------------------------
# Base setup
# ------------------------------------------------------
apply_base_config()
render_sidebar()

session = get_session()  # not used yet, but will be once DB wiring is in

# ------------------------------------------------------
# Session state for planning
# ------------------------------------------------------
if "planned_recipes" not in st.session_state:
    # store {recipe_id: {"title": ..., "date": None}}
    st.session_state.planned_recipes = {}

if "rec_page" not in st.session_state:
    st.session_state.rec_page = 0  # for simple paging instead of a true JS carousel


# ------------------------------------------------------
# PAGE HEADER
# ------------------------------------------------------
header_cols = st.columns([7, 1])
with header_cols[0]:
    st.title("📅 Planning Dashboard")
    st.caption("Plan meals, reduce waste, and optimize your pantry.")

with header_cols[1]:
    st.button("🔄 Refresh", help="Will re-run recommendations once model is wired")


# ------------------------------------------------------
# 🔎 Recommendation Filters (UI only for now)
# ------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Recommendation Filters")
with col2:
    filter_cols = st.columns([2, 2, 6])
    with filter_cols[0]:
        max_missing = st.selectbox(
            "Max Missing Ingredients",
            [0, 1, 2, 3],
            index=1,
        )
with col3:
    st.write("Place Holder for a Visual Maybe")

# ------------------------------------------------------
# Placeholder recommendations
# (Replace this with a call to RecipeRecommender later)
# ------------------------------------------------------
dummy_recommendations = [
    {
        "recipe_id": 1,
        "title": "Garlic Ginger Rice",
        "score": 18.4,
        "matched": 4,
        "missing": 1,
        "external": 0,
    },
    {
        "recipe_id": 2,
        "title": "Sheet Pan Chicken & Veggies",
        "score": 16.9,
        "matched": 5,
        "missing": 2,
        "external": 1,
    },
    {
        "recipe_id": 3,
        "title": "Roasted Veggie Medley",
        "score": 15.2,
        "matched": 3,
        "missing": 0,
        "external": 0,
    },
    {
        "recipe_id": 4,
        "title": "Pasta with Leftover Greens",
        "score": 14.1,
        "matched": 4,
        "missing": 1,
        "external": 0,
    },
    {
        "recipe_id": 5,
        "title": "Breakfast Scramble",
        "score": 13.0,
        "matched": 3,
        "missing": 1,
        "external": 1,
    },
    {
        "recipe_id": 6,
        "title": "Freezer Clean-Out Soup",
        "score": 12.5,
        "matched": 6,
        "missing": 3,
        "external": 2,
    },
]


# ------------------------------------------------------
# ⭐ Recommended Recipes — Pure Streamlit columns
# ------------------------------------------------------
st.markdown("## Recommended Recipes")

# Pagination config
PAGE_SIZE = 5
total_recs = len(dummy_recommendations)
total_pages = max((total_recs - 1) // PAGE_SIZE + 1, 1)

# Init tracking variable
if "rec_page" not in st.session_state:
    st.session_state.rec_page = 0

# Clamp page number
st.session_state.rec_page = min(
    max(st.session_state.rec_page, 0),
    total_pages - 1
)

# Compute range of items
start = st.session_state.rec_page * PAGE_SIZE
end = start + PAGE_SIZE
page_items = dummy_recommendations[start:end]

# ----------------- Navigation Buttons -----------------
if "rec_start_idx" not in st.session_state:
    st.session_state.rec_start_idx = 0   # beginning of the list
WINDOW_SIZE = 5
total_items = len(dummy_recommendations)

start = st.session_state.rec_start_idx
end = min(start + WINDOW_SIZE, total_items)

# Slice the window of recipes
visible_recs = dummy_recommendations[start:end]


nav = st.columns([1, 3, 1])

with nav[0]:
    if st.button("⬅️ Prev", disabled=start == 0):
        st.session_state.rec_start_idx = max(start - WINDOW_SIZE, 0)
        st.rerun()

with nav[1]:
    st.markdown(
        f"<p style='text-align:center;'>Showing {start+1}–{end} of {total_items}</p>",
        unsafe_allow_html=True
    )

with nav[2]:
    if st.button("Next ➡️", disabled=end >= total_items):
        st.session_state.rec_start_idx = min(start + WINDOW_SIZE, total_items - WINDOW_SIZE)
        st.rerun()


# ----------------- Render 5 Columns of Tiles -----------------
cols = st.columns(5)

for i, (col, rec) in enumerate(zip(cols, visible_recs)):
    recipe_id = rec["recipe_id"]
    is_added = recipe_id in st.session_state.planned_recipes

    with col:
        with st.container(border=True):

            # ----- Top: Title + Add Button -----
            title_col, btn_col = st.columns([4, 1])

            with title_col:
                st.subheader(rec["title"])

            with btn_col:
                if not is_added:
                    if st.button("➕", key=f"addtop_{recipe_id}_{i}"):
                        st.session_state.planned_recipes.append(recipe_id)
                        st.rerun()
                else:
                    st.markdown("<div style='text-align:right;'>✔️</div>", unsafe_allow_html=True)

            # ----- Recipe Info -----
            st.write(f"Score: {rec['score']}")
            st.write(f"Matched: {rec['matched']}")
            st.write(f"Missing: {rec['missing']}")
            st.write(f"External: {rec['external']}")




# ------------------------------------------------------
# 📚 All Recipes Browser (still placeholder)
# ------------------------------------------------------
st.markdown("## All Recipes")

with st.expander("Browse all recipes"):
    search_term = st.text_input("Search recipes by name or ingredient")
    st.write("_Recipe list will load here from DB later._")

    # Placeholder fake rows
    for i in range(3):
        c = st.columns([4, 1])
        with c[0]:
            st.write(f"Sample Recipe #{i+1}")
        with c[1]:
            st.button("➕", key=f"browse_add_{i}")


# ------------------------------------------------------
# 📝 Planning Queue
# ------------------------------------------------------
st.markdown("## 📝 Your Planning Queue")

if not st.session_state.planned_recipes:
    st.warning("No recipes added to the planner yet.")
else:
    for idx, rid in enumerate(st.session_state.planned_recipes, start=1):
        rec = next(r for r in dummy_recommendations if r["recipe_id"] == rid)

        with st.expander(f"{idx}. {rec['title']}"):
            date = st.date_input(
                "Choose a cooking date:",
                datetime.now().date() + timedelta(days=idx),
                key=f"date_picker_{rid}"
            )

            if st.button("✔️ Confirm & Lock In", key=f"confirm_{rid}"):
                st.success("Recipe confirmed! Pantry updated.")



# ------------------------------------------------------
# Sidebar help text (kept from your previous version)
# ------------------------------------------------------
with st.sidebar.expander("ℹ️ How Planning Works"):
    st.write(
        """
        **Planning Dashboard Workflow**
        - View top personalized recipe recommendations  
        - Filter recommendations by missing ingredient count  
        - Browse the full list of recipes  
        - Add recipes to your planning queue  
        - Assign a date to make each recipe  
        - “Confirm” a recipe to lock it in  
        - Confirmation will eventually:  
          - Add missing ingredients to your pantry  
          - Deduct ingredients that will be used  
          - Feed into waste-forecasting visualizations  
        """
    )
