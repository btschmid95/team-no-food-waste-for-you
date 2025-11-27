import matplotlib.pyplot as plt
import numpy as np
import sys
from pathlib import Path

# Make repo root importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from visuals.pantry_analytics import compute_waste_summary_from_events
except ImportError:
    from pantry_analytics import compute_waste_summary_from_events


def plot_waste_waterfall(engine) -> plt.Figure:
    """
    Overall waste vs saved (waste avoided) chart.

    - Total Wasted       = sum of trash events
    - Total Saved (Used) = sum of avoid events

    Visual:
      * One bar going DOWN from 0 (wasted, red)
      * One bar going UP from 0 (saved, green)
    """
    waste_summary = compute_waste_summary_from_events(engine)

    if waste_summary.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "No waste data available",
            ha="center",
            va="center",
            fontsize=12,
        )
        ax.axis("off")
        return fig

    # Sum across categories to get overall totals
    total_wasted = float(waste_summary["realized_waste"].fillna(0).sum())
    total_saved = float(waste_summary["avoided_waste"].fillna(0).sum())

    if total_wasted == 0 and total_saved == 0:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "No realized or avoided waste recorded yet.",
            ha="center",
            va="center",
            fontsize=12,
        )
        ax.axis("off")
        return fig

    # Make wasted negative so it points DOWN
    wasted_bar = -total_wasted
    saved_bar = total_saved

    labels = ["Realized Waste", "Avoided Waste (Food Used)"]
    values = [wasted_bar, saved_bar]
    colors = ["red", "green"]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.bar(x, values, color=colors)

    # Symmetric y-limits so up/down are visually balanced
    max_val = max(total_wasted, total_saved)
    ax.set_ylim(-max_val * 1.2, max_val * 1.2)

    ax.axhline(0, color="black", linewidth=1)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0, ha="center")
    ax.set_ylabel("Amount (pantry units)")
    ax.set_title("Overall Food Wasted vs Food Used")

    # Legend
    # waste_patch = plt.Rectangle((0, 0), 1, 1, color="red", label="Realized Waste")
    # saved_patch = plt.Rectangle((0, 0), 1, 1, color="green", label="Avoided Waste")
    # ax.legend(handles=[waste_patch, saved_patch], loc="upper right")

    plt.tight_layout()
    return fig