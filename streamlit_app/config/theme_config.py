import streamlit as st

def apply_base_config():
    st.set_page_config(
        page_title="No Food Waste for You",
        page_icon="🥘",
        layout="wide",
        initial_sidebar_state="expanded",
    )

THEME = {
    "primaryColor": "#2A7FFF",
    "backgroundColor": "#FAFAFA",
    "secondaryBackgroundColor": "#FFFFFF",
    "textColor": "#333333",
}