import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Pricing", layout="wide")

st.title("Pricing")
st.write("Trader Joe's Products")

csv_path = "../web_scraper/trader_joes_products.csv"

try:
    df = pd.read_csv(csv_path)

    if "Link" in df.columns:
        df = df.drop(columns=["Link"])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=800,
        column_config={
            "url": st.column_config.LinkColumn(
                "Product URL",
                help="Click to view the Trader Joe's product page"
            )
        }
    )

except FileNotFoundError:
    st.error(f"File not found at {csv_path}")