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
    Overall waterfall chart of food wasted vs food used (waste avoided).

    Uses pantry_event + pantry + tj_inventory via
    compute_waste_summary_from_events(engine).

    Bars:
      - Total Wasted  (down from zero)
      - Total Saved   (up toward zero from wasted baseline)
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

    # Sum across all categories to get overall totals
    total_wasted = float(waste_summary["realized_waste"].fillna(0).sum())
    total_saved = float(waste_summary["avoided_waste"].fillna(0).sum())

    # If we truly have nothing, bail out nicely
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

    # Waterfall steps (relative changes)
    # negative = wasted, positive = saved
    steps = [-total_wasted, total_saved]
    labels = ["Total Wasted", "Total Saved (Food Used)"]
    colors = ["red", "green"]

    x = np.arange(len(steps))

    fig, ax = plt.subplots(figsize=(10, 5))

    cumulative = 0.0
    for i, (step, label, color) in enumerate(zip(steps, labels, colors)):
        # Each bar starts at current cumulative level
        bottom = cumulative
        ax.bar(x[i], step, bottom=bottom, color=color)
        cumulative += step

    # Formatting
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0, ha="center")
    ax.set_ylabel("Amount (pantry units)")
    ax.set_title("Overall Waste vs Food Used (Waterfall)")

    # Add horizontal line at 0 for reference
    ax.axhline(0, color="black", linewidth=1)

    # Legend (color meaning)
    waste_patch = plt.Rectangle((0, 0), 1, 1, color="red", label="Wasted")
    saved_patch = plt.Rectangle((0, 0), 1, 1, color="green", label="Saved (Waste Avoided)")
    ax.legend(handles=[waste_patch, saved_patch], loc="upper right")

    plt.tight_layout()
    return fig