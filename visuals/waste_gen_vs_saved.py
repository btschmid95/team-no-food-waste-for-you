import matplotlib.pyplot as plt
import numpy as np
import sys
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------
# Make repo root importable (for running this file directly)
# For .../team-no-food-waste-for-you/visuals/waste_gen_vs_saved.py
# parents[0] = visuals/, parents[1] = repo root
# ---------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Try both styles in case "visuals" is or isn't treated as a package
try:
    from visuals.pantry_analytics import compute_waste_summary_from_events
except ImportError:
    from pantry_analytics import compute_waste_summary_from_events


def plot_waste_waterfall(engine) -> plt.Figure:
    """
    Stacked bar chart of realized vs saved waste by category.

    (We keep the function name 'plot_waste_waterfall' so the rest of
    the app doesn't need to change, but it's now a stacked bar chart.)
    """
    waste_summary = compute_waste_summary_from_events(engine)

    if waste_summary.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5, 0.5,
            "No waste data available",
            ha="center", va="center", fontsize=12
        )
        ax.axis("off")
        return fig

    df = waste_summary.copy()

    # Sort by realized waste so biggest categories come first
    df = df.sort_values("realized_waste", ascending=False)

    categories = df["category"].tolist()
    wasted = df["realized_waste"].fillna(0).astype(float).to_numpy()
    saved = df["avoided_waste"].fillna(0).astype(float).to_numpy()

    x = np.arange(len(categories))

    fig, ax = plt.subplots(figsize=(10, 5))

    # Bottom segment: wasted (red)
    ax.bar(x, wasted, color="red", label="Wasted")

    # Top segment: saved (green), stacked on wasted
    ax.bar(x, saved, bottom=wasted, color="green", label="Saved")

    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45, ha="right")
    ax.set_ylabel("Amount (units)")
    ax.set_title("Realized vs Saved Waste by Category (Stacked)")

    ax.legend(loc="upper right")
    plt.tight_layout()

    return fig


# ----- Standalone test so you can run: python visuals/waste_gen_vs_saved.py -----
if __name__ == "__main__":
    # Example fake data to visualize layout
    example = pd.DataFrame(
        {
            "category": ["Produce", "Dairy", "Frozen"],
            "realized_waste": [10, 5, 2],
            "avoided_waste": [3, 0, 1],
        }
    )

    # Plot using the same logic but without needing a DB engine
    df = example.sort_values("realized_waste", ascending=False)
    categories = df["category"].tolist()
    wasted = df["realized_waste"].fillna(0).astype(float).to_numpy()
    saved = df["avoided_waste"].fillna(0).astype(float).to_numpy()

    x = np.arange(len(categories))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x, wasted, color="red", label="Wasted")
    ax.bar(x, saved, bottom=wasted, color="green", label="Saved")

    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45, ha="right")
    ax.set_ylabel("Amount (units)")
    ax.set_title("Standalone Test: Realized vs Saved Waste (Stacked)")
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.show()