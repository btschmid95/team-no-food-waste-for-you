import streamlit as st
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from pathlib import Path
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

apply_base_config()
render_sidebar()

st.title("📅 Planning Dashboard")

st.subheader("Recommended Recipes")
st.write("Recipe recommendations will show here soon!")
