import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# Make repo root importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from visuals.pantry_analytics import (
        load_pantry_with_category,
        get_forecast_waste_by_date,
    )
except ImportError:
    from pantry_analytics import (
        load_pantry_with_category,
        get_forecast_waste_by_date,
    )


def plot_consumption_vs_waste(engine, recipe_mgr):
    """
    Visual 2:
    Planned Consumption vs Forecast Unplanned Waste (next 30 days).

    - Forecast waste is computed from pantry expirations.
    - Planned consumption comes from recipe_mgr.get_planned_consumption_by_date().
    - Unplanned waste = max(forecast_waste - planned_consumption, 0).
    """

    # ---------- 1) Load pantry + forecast waste ----------
    pantry_df = load_pantry_with_category(engine)
    if pantry_df is None or pantry_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5, 0.5,
            "No pantry data available.",
            ha="center", va="center", fontsize=12
        )
        ax.axis("off")
        return fig

    forecast_df = get_forecast_waste_by_date(pantry_df)  # date, forecast_waste

    # ---------- 2) Planned consumption from recipes ----------
    cons_df = recipe_mgr.get_planned_consumption_by_date()  # date, planned_consumption

    if forecast_df.empty and cons_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5, 0.5,
            "No forecast waste or planned consumption\nfor the upcoming period.",
            ha="center", va="center", fontsize=12
        )
        ax.axis("off")
        return fig

    # Ensure datetime
    if not forecast_df.empty:
        forecast_df["date"] = pd.to_datetime(forecast_df["date"])
    if not cons_df.empty:
        cons_df["date"] = pd.to_datetime(cons_df["date"])

    # ---------- 3) Merge + restrict to next 30 days ----------
    df = (
        pd.merge(forecast_df, cons_df, on="date", how="outer")
          .sort_values("date")
    )

    today = pd.Timestamp.today().normalize()
    horizon_end = today + pd.Timedelta(days=30)
    mask = (df["date"] >= today) & (df["date"] <= horizon_end)
    if mask.any():
        df = df[mask]

    df["forecast_waste"] = df["forecast_waste"].fillna(0)
    df["planned_consumption"] = df["planned_consumption"].fillna(0)

    # ---------- 4) Compute unplanned waste ----------
    df["unplanned_waste"] = (df["forecast_waste"] - df["planned_consumption"]).clip(lower=0)

    if (df["unplanned_waste"] == 0).all() and (df["planned_consumption"] == 0).all():
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5, 0.5,
            "No unplanned waste or planned consumption\nin the next 30 days.",
            ha="center", va="center", fontsize=12
        )
        ax.axis("off")
        return fig

    # ---------- 5) Plot: unplanned waste vs planned consumption ----------
    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Left axis: unplanned waste
    ax1.plot(
        df["date"],
        df["unplanned_waste"],
        label="Forecasted Waste",
        linewidth=2,
    )
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Forecasted Waste (pantry units)")

    # Right axis: planned consumption
    ax2 = ax1.twinx()
    ax2.plot(
        df["date"],
        df["planned_consumption"],
        linestyle="--",
        linewidth=2,
        color="orange",
        label="Planned Consumption",
    )
    ax2.set_ylabel("Planned Consumption (pantry units)")

    fig.suptitle("Planned Consumption vs Forecasted Waste (Food Without a Recipe)")
    fig.autofmt_xdate()

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.tight_layout()
    return fig