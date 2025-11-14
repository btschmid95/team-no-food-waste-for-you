import streamlit as st

def render_sidebar():
    st.sidebar.title("🍽️ Team No Food Waste For You")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📌 Navigation")

    page = st.sidebar.radio(
        "Go to:",
        options=["home", "planner", "pantry"],
        format_func=lambda p: {
            "home": "🏠 Home",
            "planner": "📅 Planning Dashboard",
            "pantry": "🥫 Pantry Dashboard",
        }[p],
    )

    st.sidebar.markdown("---")

    return page
