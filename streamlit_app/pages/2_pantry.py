import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

st.set_page_config(layout="wide", page_title="My Pantry Swarm Comparison")

@st.cache_data
def load_products():
    return pd.read_csv("streamlit_app/trader_joes_products.csv")

products_df = load_products()

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

def force_layout(
    circles,
    k_repel=0.45,
    k_anchor=0.8,
    k_gravity=0.5  ,
    gravity_scale=5,  # power factor for radius influence
    x_bias=0.05,
    y_bias=2,
    iterations=5000,
    x_scale=0.35,
    jitter=0.5,
    center_boost=10
):
    """
    Force-directed relaxation with directional bias and mass-weighted gravity.
    - Temporarily compresses X by x_scale so overlaps are more likely to be found
    - Adds small Y jitter to break perfect symmetry
    - Repels overlapping circles (within same category)
    - Applies mass-weighted gravity to pull larger circles toward their y0
    - Restores X scale at the end
    Adjust parameters to taste.
    """
    # compress x and jitter y to break symmetry
    for c in circles:
        c["x"] *= x_scale
        c["y"] += np.random.uniform(-jitter, jitter)

    for _ in range(iterations):
        # Repulsion between overlapping circles (only within same category)
        for i in range(len(circles)):
            for j in range(i + 1, len(circles)):
                ci, cj = circles[i], circles[j]
                if ci["cat"] != cj["cat"]:
                    continue
                dx = ci["x"] - cj["x"]
                dy = ci["y"] - cj["y"]
                dist = np.hypot(dx, dy)
                min_dist = ci["r"] + cj["r"]
                if dist < min_dist and dist > 1e-6:
                    overlap = (min_dist - dist)
                    overlap_frac = (min_dist - dist) / min_dist
                    base_force = k_repel * (overlap_frac ** 2)

                    # Boost if one center lies inside another
                    if dist < min(ci["r"], cj["r"]):
                        base_force *= center_boost**(3/2)


                    nx, ny = dx / dist, dy / dist
                    # bias movement more in Y than X (x_bias small keeps them near x0)
                    ci["x"] += nx * base_force * 0.5 * x_bias
                    ci["y"] += ny * base_force * 0.5 * y_bias
                    cj["x"] -= nx * base_force * 0.5 * x_bias
                    cj["y"] -= ny * base_force * 0.5 * y_bias

        # Gentle gravity pull toward category baseline (mass-weighted)
        for c in circles:
            g = k_gravity * (c["r"] ** gravity_scale)
            c["y"] += (c["y0"] - c["y"]) * g

        # Weak anchor back to original X (keep near x0)
        for c in circles:
            c["x"] += (c["x0"] - c["x"]) * k_anchor

    # Restore X scaling
    for c in circles:
        c["x"] /= x_scale

def set_equal_aspect(ax, xlim, ylim, margin=0.08):
    x_range = xlim[1] - xlim[0]
    y_range = ylim[1] - ylim[0]
    ax.set_xlim(xlim[0] - margin * x_range, xlim[1] + margin * x_range)
    ax.set_ylim(ylim[0] - margin * y_range, ylim[1] + margin * y_range)
    ax.set_aspect('equal', adjustable='datalim')

if st.button("Generate Random Pantry"):
    st.session_state['pantry'] = generate_random_pantry(products_df)

pantry_df = st.session_state.get('pantry', pd.DataFrame())

st.subheader("Pantry Swarm Layout Comparison")

tab1, tab2 = st.tabs(["Pantry Table", "Pantry Expiration Visual"])

with tab1:
    if not pantry_df.empty:
        st.dataframe(pantry_df)
    else:
        st.info("Generate your pantry to see the table.")

with tab2:
    cutoff_days = 3
    if not pantry_df.empty:
        # create sorted df (you can adjust sorting strategy)
        df_sorted = pantry_df.sort_values(['days_to_expire', 'quantity'], ascending=[False, False]).copy()
        max_quantity = df_sorted['quantity'].max()

        # spacing between category baseline lines (increase for more vertical room)
        y_spacing = 40
        unique_cats = df_sorted['category'].unique()
        category_offsets = {cat: i * y_spacing for i, cat in enumerate(unique_cats)}

        # create circles list
        circles = []
        for _, row in df_sorted.iterrows():
            x0 = row['days_to_expire']
            y0 = category_offsets[row['category']]
            circles.append({
                "x": x0,
                "y": y0,
                "x0": x0,
                "y0": y0,
                "r": row['quantity'] / 3.0,  # scale radius for visuals
                "cat": row['category'],
                "label": row.get('product_name', '')
            })

        # run force relax
        force_layout(
            circles,
            k_repel=0.4,
            k_anchor=0.02,
            k_gravity=0.05,
            gravity_scale=1.2,
            x_bias=0.02,
            y_bias=2,
            iterations=600,
            x_scale=0.35,
            jitter=0.45
        )

        # Plot
        fig, ax = plt.subplots(figsize=(12, 7))
        for c in circles:
            circ = Circle((c["x"], c["y"]), c["r"], alpha=0.6,
                          color=f"C{list(category_offsets.keys()).index(c['cat']) % 10}")
            ax.add_patch(circ)
            # optional label:
            # ax.text(c["x"], c["y"], c["label"], ha='center', va='center', fontsize=6)

        # axes limits and aspect
        xlim = (0, max(df_sorted['days_to_expire'].max() + 2, 10))
        ylim = (-10, (len(category_offsets)) * y_spacing + 30)
        set_equal_aspect(ax, xlim, ylim)

        ax.invert_xaxis()
        ax.set_xlabel("Days until Expiration")
        ax.set_ylabel("Category Cluster")
        ax.set_title("Pantry Expiration (Force-Directed Bubble Layout)")
        ax.grid(True)

        # category labels on the right
        x_label_pos = xlim[1] + 1
        for cat, offset in category_offsets.items():
            ax.text(x_label_pos, offset, cat, va='center', fontsize=10, fontweight='bold')

        # cutoff line (optional)
        ax.axvline(cutoff_days, color='red', linestyle='--', label=f'{cutoff_days}-day cutoff')

        st.pyplot(fig)
    else:
        st.info("Generate your pantry to see the plot.")
