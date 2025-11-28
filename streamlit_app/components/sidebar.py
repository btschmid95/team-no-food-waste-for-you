import streamlit as st

def render_sidebar():
    st.sidebar.page_link('streamlit_app.py', label='Home')
    
    st.sidebar.page_link("pages/pantry.py", label="Pantry Dashboard")
    st.sidebar.page_link("pages/planner.py", label="Planning Dashboard")

    st.sidebar.markdown("---")
    st.sidebar.caption("Team No Food Waste For You")