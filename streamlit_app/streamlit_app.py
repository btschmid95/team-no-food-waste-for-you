# streamlit_app.py

import streamlit as st
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repo's root directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from database.tables import PantryItem, RecipeSelected

# --- Page setup ---
st.set_page_config(
    page_title="Team No Food Waste",
    page_icon="🥕",
    layout="wide",
)
#st.sidebar.page_link('streamlit_app.py', label='Home')
apply_base_config()
render_sidebar()

# --- Home Page Content ---
st.title("🏠 Home Dashboard")

session = get_session()

# Example metrics
total_items = session.query(PantryItem).count()
planned_recipes = session.query(RecipeSelected).count()

col1, col2 = st.columns(2)
col1.metric("Total Pantry Items", total_items)
col2.metric("Recipes Planned", planned_recipes)

st.markdown("### 👀 More insights coming soon...")
