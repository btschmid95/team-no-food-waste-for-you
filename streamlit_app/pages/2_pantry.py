import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import math
import random

st.set_page_config(layout="wide", page_title="Pantry")

# --- Node class ---
class Node:
    def __init__(self, x, y, r, category, label, days_to_expire):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.r = r
        self.category = category
        self.label = label
        self.days_to_expire = days_to_expire

def jiggle():
    return (random.random() - 0.5) * 1e-6

def force_collide(nodes, iterations=1, strength=1.0):
    n = len(nodes)
    for _ in range(iterations):
        for i in range(n):
            a = nodes[i]
            for j in range(i + 1, n):
                b = nodes[j]
                dx = (a.x + a.vx) - (b.x + b.vx)
                dy = (a.y + a.vy) - (b.y + b.vy)
                if dx == 0 and dy == 0:
                    dx = jiggle()
                    dy = jiggle()
                dist2 = dx*dx + dy*dy
                r = a.r + b.r
                if dist2 < r*r:
                    dist = math.sqrt(dist2)
                    if dist == 0:
                        dist = r - 1e-6
                    overlap = (r - dist) / dist * strength
                    dx *= overlap
                    dy *= overlap
                    w_a = b.r*b.r / (a.r*a.r + b.r*b.r)
                    w_b = 1 - w_a
                    a.vx += dx * w_a
                    a.vy += dy * w_a
                    b.vx -= dx * w_b
                    b.vy -= dy * w_b
    for node in nodes:
        node.x += node.vx
        node.y += node.vy
        node.vx *= 0.8
        node.vy *= 0.8

# --- Load products ---
@st.cache_data
def load_products():
    return pd.read_csv("streamlit_app/trader_joes_products.csv")

products_df = load_products()

# --- Placeholder standard expiration dict ---
# In reality, this would be pulled from a database.
STANDARD_EXPIRATION = {name: np.random.randint(3, 30) for name in products_df['product_name'].unique()}

# --- Session state for pantry ---
if "pantry_df" not in st.session_state:
    st.session_state["pantry_df"] = pd.DataFrame()

# --- Function to add items ---
def add_item_to_pantry(product_name, category, quantity=1, purchase_date=None):
    purchase_date = purchase_date or datetime.now()
    standard_expiration = STANDARD_EXPIRATION.get(product_name, 7)  # default 7 days
    expiration_date = purchase_date + timedelta(days=standard_expiration)
    new_row = pd.DataFrame([{
        "product_name": product_name,
        "category": category,
        "quantity": quantity,
        "purchase_date": purchase_date,
        "expiration_date": expiration_date,
        "days_to_expire": (expiration_date - pd.Timestamp.now()).total_seconds()/86400.0
    }])
    st.session_state["pantry_df"] = pd.concat([st.session_state["pantry_df"], new_row], ignore_index=True)

# --- Tabs ---
tab1, tab2 = st.tabs(["View Pantry", "Add Items"])

with tab1:
    st.header("Pantry Bubble Swarm")

    # Button to generate random pantry if empty
    if st.button("Generate Random Pantry") and st.session_state["pantry_df"].empty:
        meats = products_df[products_df['category'].str.contains("Meat, Seafood & Plant-Based", case=False, na=False)].sample(20, replace=True)
        veggies = products_df[products_df['category'].str.contains("Fresh Fruits & Veggies", case=False, na=False)].sample(20, replace=True)
        random_pantry = pd.concat([meats, veggies]).copy()
        random_pantry['quantity'] = np.random.randint(1, 5, len(random_pantry))
        random_pantry['purchase_date'] = datetime.now()
        random_pantry['expiration_date'] = random_pantry['product_name'].map(lambda p: datetime.now() + timedelta(days=STANDARD_EXPIRATION.get(p,7)))
        random_pantry['days_to_expire'] = (random_pantry['expiration_date'] - pd.Timestamp.now()).dt.total_seconds()/86400.0
        st.session_state["pantry_df"] = random_pantry.reset_index(drop=True)

    # Only show visualization if pantry has items
    if not st.session_state["pantry_df"].empty:
        df = st.session_state["pantry_df"]

        # --- Category bands ---
        categories = df['category'].unique()
        category_spacing = 10
        targets = {cat: (0.5, 0.1 + i*category_spacing) for i, cat in enumerate(categories)}

        # --- Nodes ---
        nodes = []
        for _, row in df.iterrows():
            nodes.append(Node(
                x=row['days_to_expire'],
                y=targets[row['category']][1] + np.random.uniform(-0.1,0.1),
                r=row['quantity']/5,
                category=row['category'],
                label=row['product_name'],
                days_to_expire=row['days_to_expire']
            ))

        # --- Force simulation ---
        def get_gravity_hub(x, hub_spacing=1.0):
            return round(x/hub_spacing)*hub_spacing

        for step in range(300):
            for node in nodes:
                cx, cy = targets[node.category]
                node.vy += (cy - node.y) * 0.15
                hub_x = get_gravity_hub(node.days_to_expire, hub_spacing=1.0)
                node.vx += (hub_x - node.x) * 0.3
            force_collide(nodes, iterations=5, strength=0.8)

        # --- Plot ---
        palette = ["#1f77b4","#2ca02c","#9467bd","#ff7f0e","#8c564b","#e377c2","#7f7f7f","#17becf","#bcbd22","#aec7e8"]
        category_colors = {cat: palette[i % len(palette)] for i, cat in enumerate(categories)}

        fig = go.Figure()
        fig.add_vline(
            x=0,
            line=dict(color="red", width=2, dash="dash"),
            annotation_text="Today",
            annotation_position="top right",
            annotation_font=dict(color="red", size=14)
        )

        marker_scale = 40
        for cat in categories:
            x = [n.x for n in nodes if n.category==cat]
            y = [n.y for n in nodes if n.category==cat]
            r = [n.r*marker_scale for n in nodes if n.category==cat]
            colors = ["lightcoral" if n.days_to_expire<0 else category_colors[cat] for n in nodes if n.category==cat]
            fig.add_trace(go.Scatter(
                x=x, y=y, mode="markers",
                marker=dict(size=r, color=colors, opacity=0.7, line=dict(width=1,color="white"), sizemode="diameter"),
                name=cat,
                text=[n.label for n in nodes if n.category==cat],
                customdata=[n.days_to_expire for n in nodes if n.category==cat],
                hovertemplate="<b>%{text}</b><br>Days until Expiration: %{customdata:.1f}<br>Qty: %{marker.size}<extra></extra>"
            ))

        # Category labels
        for cat in categories:
            fig.add_annotation(
                x=-25, y=targets[cat][1],
                text=cat, showarrow=False,
                xanchor="right", yanchor="middle",
                font=dict(size=20, color="black")
            )

        # Expand X-axis
        x_margin = 8
        xmin = df['days_to_expire'].min() - x_margin
        xmax = df['days_to_expire'].max() + x_margin
        fig.update_xaxes(range=[xmin,xmax])

        fig.update_layout(
            title="Pantry Bubble Swarm — Days until Expiration",
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white",
            width=1400,
            height=600,
            showlegend=False
        )
        fig.update_yaxes(scaleanchor="x", scaleratio=1)
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Add Item to Pantry")
    product_name = st.selectbox("Select Product", products_df['product_name'].unique())
    category = products_df.loc[products_df['product_name']==product_name, 'category'].values[0]
    quantity = st.number_input("Quantity", min_value=1, max_value=50, value=1)
    purchase_date = st.date_input("Purchase Date", datetime.now().date())
    
    if st.button("Add Item"):
        add_item_to_pantry(product_name, category, quantity, purchase_date)
        st.success(f"Added {quantity} x {product_name} to pantry.")
