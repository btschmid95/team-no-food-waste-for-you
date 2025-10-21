import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Pricing", layout="wide")
st.write("Trader Joe's Products")

csv_path = os.path.join("..", "web_scraper", "trader_joes_products.csv")

try:
    df = pd.read_csv(csv_path)
    st.dataframe(df,use_container_width=True, hide_index=True)
except FileNotFoundError:
    st.error(f"File not found at {csv_path}")