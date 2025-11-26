# import matplotlib.pyplot as plt
# import numpy as np
# import sys
# from pathlib import Path
# import pandas as pd
#
# # Make repo root importable
# ROOT = Path(__file__).resolve().parents[2]
# if str(ROOT) not in sys.path:
#     sys.path.append(str(ROOT))
#
# def plot_waste_waterfall(engine):
#     from visuals.pantry_analytics import compute_waste_summary_from_events
#
#     waste_summary = compute_waste_summary_from_events(engine)
#     """
#     Visual 3:
#     Waterfall-style bar chart of realized vs avoided waste by category.
#     """
#     df = waste_summary.copy()
#     df = df.sort_values("realized_waste", ascending=False)
#
#     steps = []
#     labels = []
#
#     cumulative = 0
#
#     steps.append(0)
#     labels.append("Start")
#
#     for _, row in df.iterrows():
#         cat = row["category"]
#         realized = row["realized_waste"]
#         avoided = row["avoided_waste"]
#
#         # negative bar = realized waste
#         steps.append(-realized)
#         labels.append(f"{cat} wasted")
#
#         # positive bar = avoided waste (currently 0, but kept for future use)
#         if avoided != 0:
#             steps.append(avoided)
#             labels.append(f"{cat} avoided")
#
#     x = np.arange(len(labels))
#
#     fig, ax = plt.subplots(figsize=(10, 5))
#
#     prev = 0
#     for i, step in enumerate(steps):
#         color = "red" if step < 0 else "green"
#         ax.bar(x[i], step, bottom=prev, color=color)
#         prev += step
#
#     ax.set_xticks(x)
#     ax.set_xticklabels(labels, rotation=45, ha="right")
#     ax.set_ylabel("Waste (amount units)")
#     ax.set_title("Realized vs Avoided Waste by Category (Simple Approximation)")
#     plt.tight_layout()
#     return fig


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
    # Fallback if visuals/ is on sys.path directly
    from pantry_analytics import compute_waste_summary_from_events


def _build_waterfall_df(waste_summary: pd.DataFrame) -> pd.DataFrame:
    """
    Convert waste_summary into labels + signed steps for the waterfall.

    - realized_waste -> always NEGATIVE (down, 'waste')
    - avoided_waste  -> always POSITIVE (up, 'saved')

    Each category label is reused for waste + saved bars.
    """
    df = waste_summary.copy()
    df = df.sort_values("realized_waste", ascending=False)

    labels = []
    steps = []
    kinds = []   # 'waste' or 'saved' for coloring / legend

    for _, row in df.iterrows():
        cat = row["category"]
        realized = float(row["realized_waste"] or 0)
        avoided = float(row["avoided_waste"] or 0)

        # Treat DB values as magnitudes; we control the sign
        waste_step = -abs(realized)   # always down
        saved_step = abs(avoided)     # always up

        if realized != 0:
            labels.append(cat)
            steps.append(waste_step)
            kinds.append("waste")

        if avoided != 0:
            labels.append(cat)
            steps.append(saved_step)
            kinds.append("saved")

    if not labels:
        labels = ["No data"]
        steps = [0.0]
        kinds = ["waste"]

    return pd.DataFrame({"label": labels, "step": steps, "kind": kinds})


def plot_waste_waterfall(engine) -> plt.Figure:
    """
    Waterfall-style bar chart of realized vs saved waste by category.
    Red bars = wasted (down), green bars = saved (up).
    """
    waste_summary = compute_waste_summary_from_events(engine)

    if waste_summary.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No waste data available",
                ha="center", va="center", fontsize=12)
        ax.axis("off")
        return fig

    wf_df = _build_waterfall_df(waste_summary)

    x = np.arange(len(wf_df))
    steps = wf_df["step"].to_numpy()
    labels = wf_df["label"].tolist()
    kinds = wf_df["kind"].tolist()

    fig, ax = plt.subplots(figsize=(10, 5))

    cumulative = 0.0
    for i, (step, kind) in enumerate(zip(steps, kinds)):
        # kind controls color; sign already enforced
        color = "red" if kind == "waste" else "green"
        ax.bar(x[i], step, bottom=cumulative, color=color)
        cumulative += step

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Waste (amount units)")
    ax.set_title("Realized vs Saved Waste by Category")

    # Legend: red = wasted, green = saved
    waste_patch = plt.Rectangle((0, 0), 1, 1, color="red", label="Wasted")
    saved_patch = plt.Rectangle((0, 0), 1, 1, color="green", label="Saved")
    ax.legend(handles=[waste_patch, saved_patch], loc="upper right")

    plt.tight_layout()
    return fig

# Optional: quick standalone test when you run this file directly
if __name__ == "__main__":
    # Dummy example data for sanity-checking the plot
    example = pd.DataFrame(
        {
            "category": ["Produce", "Dairy", "Frozen"],
            "realized_waste": [10, 5, 2],
            "avoided_waste": [3, 0, 1],
        }
    )

    wf_df = _build_waterfall_df(example)

    x = np.arange(len(wf_df))
    steps = wf_df["step"].to_numpy()
    labels = wf_df["label"].tolist()

    fig, ax = plt.subplots(figsize=(10, 5))
    cumulative = 0.0
    for i, step in enumerate(steps):
        color = "red" if step < 0 else "green"
        ax.bar(x[i], step, bottom=cumulative, color=color)
        cumulative += step

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Waste (amount units)")
    ax.set_title("Standalone Test: Realized vs Saved Waste")

    # Legend
    waste_patch = plt.Rectangle((0, 0), 1, 1, color="red", label="Wasted")
    saved_patch = plt.Rectangle((0, 0), 1, 1, color="green", label="Saved")
    ax.legend(handles=[waste_patch, saved_patch], loc="upper right")

    plt.tight_layout()
    plt.show()