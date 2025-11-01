import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(layout="wide", page_title="My Pantry Swarm Comparison")

@st.cache_data
def load_products():
    return pd.read_csv("streamlit_app/trader_joes_products.csv")

products_df = load_products()

# ---- Generate Random Pantry ----
def generate_random_pantry(products_df):
    meats = products_df[products_df['category'].str.contains("Meat, Seafood & Plant-Based", case=False, na=False)].sample(25, replace=True)
    veggies = products_df[products_df['category'].str.contains("Fresh Fruits & Veggies", case=False, na=False)].sample(25, replace=True)
    pantry = pd.concat([meats, veggies]).copy()
    pantry['quantity'] = np.random.randint(1, 32, len(pantry))
    pantry['expiration_date'] = [
        datetime.now() + timedelta(days=np.random.randint(-3, 27), hours=np.random.randint(0, 24))
        for _ in range(len(pantry))
    ]
    pantry['days_to_expire'] = (pantry['expiration_date'] - pd.Timestamp.now()).dt.total_seconds() / 86400.0
    return pantry.reset_index(drop=True)

if st.button("Generate Random Pantry"):
    st.session_state['pantry'] = generate_random_pantry(products_df)

pantry_df = st.session_state.get('pantry', pd.DataFrame())

st.subheader("Pantry Swarm Layout Comparison")

# Create tabs
tab1, tab2 = st.tabs(["Pantry Table", "Pantry Expiration Visual"])

# --- Tab 1: DataFrame ---
with tab1:
    if not pantry_df.empty:
        st.dataframe(pantry_df)
    else:
        st.info("Generate your pantry to see the table.")

# --- Tab 2: Swarm Plot ---
with tab2:
    cutoff_days = 3
    if not pantry_df.empty:
        fig, ax = plt.subplots(figsize=(12,6))

        # Sort by days_to_expire and quantity
        df_sorted = pantry_df.sort_values(['days_to_expire','quantity'], ascending=[False, False]).copy()
        positions = []
        max_quantity = df_sorted['quantity'].max()
        category_starts = {"Meat, Seafood & Plant-Based": 1, "Fresh Fruits & Veggies": 2}

        for idx, row in df_sorted.iterrows():
            x = row['days_to_expire']
            r = row['quantity'] / 2  # approximate radius
            y_cat = category_starts[row['category']]
            y = y_cat * max_quantity

            positions.append((x, y, r))
            df_sorted.loc[idx, 'x_pos'] = x
            df_sorted.loc[idx, 'y_pos'] = y

        df_sorted['s'] = np.pi * (df_sorted['quantity'])**2

        ax.scatter(
            df_sorted['x_pos'], df_sorted['y_pos'],
            s=df_sorted['s'],
            c=pd.factorize(df_sorted['category'])[0],
            alpha=0.7
        )

        y_min = df_sorted['y_pos'].min()
        y_max = df_sorted['y_pos'].max()
        padding = 15
        ax.set_ylim(y_min - padding, y_max + padding)
        ax.invert_xaxis()
        ax.axvline(cutoff_days, color='red', linestyle='--', label=f'{cutoff_days}-day cutoff')
        ax.set_xlabel("Days until Expiration")
        ax.set_ylabel("Y Position / Category Cluster")
        ax.set_title("Pantry Expiration visual")
        ax.grid(True)
        st.pyplot(fig)
    else:
        st.info("Generate your pantry to see the plot.")
