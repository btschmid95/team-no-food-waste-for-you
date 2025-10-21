import streamlit as st
import pandas as pd

st.title("Pricing")
st.write("Trader Joe's Products")

try:
    df = pd.read_csv("trader_joes_products.csv")
    st.dataframe(df)
except FileNotFoundError:
    st.error("File 'trader_joes_products.csv' not found. Please check your path.")