import streamlit as st
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session
from pathlib import Path
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))
from database.tables import PantryItem, TJInventory

apply_base_config()
render_sidebar()
session = get_session()

st.title("🥫 Pantry Dashboard")

pantry_items = session.query(PantryItem).all()

rows = [
    {
        "item": item.product.name,
        "amount": item.amount,
        "unit": item.unit,
        "added": item.date_added,
        "expires": item.expiration_date,
    }
    for item in pantry_items
]

st.dataframe(rows)
