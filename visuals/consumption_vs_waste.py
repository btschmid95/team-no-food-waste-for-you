import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# Make repo root importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


def plot_consumption_vs_waste(pantry_df, engine):
    """
    Visual 2: Dual-axis line chart.

    Shows the interaction between:
      - Forecast Waste (from pantry expirations)
      - Actual Consumption (from pantry_event 'consume')
      - Planned Consumption via recipes (from recipe_selected + ingredient)

    Variables:
      - Consumption via Recipe at time X
      - Waste
      - Time
    """
    from .pantry_analytics import (
        get_forecast_waste_by_date,
        get_planned_consumption_by_date,
    )

    # -----------------------------
    # 1) Forecast waste (from pantry)
    # -----------------------------
    if pantry_df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(
            0.5,
            0.5,
            "No pantry data available.\nAdd items to view forecast.",
            ha="center",
            va="center",
            fontsize=12,
        )
        ax.set_axis_off()
        return fig

    forecast_df = get_forecast_waste_by_date(pantry_df)
    if forecast_df.empty:
        forecast_df = pd.DataFrame(columns=["date", "forecast_waste"])
    forecast_df["date"] = pd.to_datetime(forecast_df["date"], errors="coerce")

    # -----------------------------
    # 2) Actual consumption (events)
    # -----------------------------
    cons_q = """
        SELECT 
            DATE(pe.timestamp) AS date,
            SUM(pe.amount)     AS total_consumed
        FROM pantry_event pe
        WHERE pe.event_type = 'consume'
        GROUP BY DATE(pe.timestamp)
        ORDER BY DATE(pe.timestamp)
    """
    cons_df = pd.read_sql(cons_q, engine)

    if cons_df.empty:
        cons_df = pd.DataFrame(columns=["date", "total_consumed"])

    cons_df["date"] = pd.to_datetime(cons_df["date"], errors="coerce")
    cons_df["total_consumed"] = pd.to_numeric(cons_df["total_consumed"], errors="coerce").fillna(0)
    cons_df = cons_df.rename(columns={"total_consumed": "actual_consumption"})

    # -----------------------------
    # 3) Planned consumption (recipes)
    # -----------------------------
    planned_df = get_planned_consumption_by_date(engine)
    if planned_df.empty:
        planned_df = pd.DataFrame(columns=["date", "planned_consumption"])
    planned_df["date"] = pd.to_datetime(planned_df["date"], errors="coerce")
    planned_df["planned_consumption"] = pd.to_numeric(
        planned_df["planned_consumption"], errors="coerce"
    ).fillna(0)

    # -----------------------------
    # 4) Merge all three timelines
    # -----------------------------
    df = (
        forecast_df.merge(cons_df, on="date", how="outer")
                   .merge(planned_df, on="date", how="outer")
                   .sort_values("date")
    )

    # Restrict to next 30 days horizon
    horizon = pd.Timestamp.today() + pd.Timedelta(days=30)
    df = df[df["date"] <= horizon]

    df["forecast_waste"] = df.get("forecast_waste", 0).fillna(0)
    df["actual_consumption"] = df.get("actual_consumption", 0).fillna(0)
    df["planned_consumption"] = df.get("planned_consumption", 0).fillna(0)

    if df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(
            0.5,
            0.5,
            "No forecast, consumption, or planned data available.",
            ha="center",
            va="center",
            fontsize=12,
        )
        ax.set_axis_off()
        return fig

    # -----------------------------
    # 5) Plot: dual-axis line chart
    # -----------------------------
    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Left axis: Waste forecast
    line_waste, = ax1.plot(
        df["date"],
        df["forecast_waste"],
        label="Forecast Waste",
        linewidth=2,
    )
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Forecast Waste (pantry units)")

    # Right axis: consumption (actual + planned)
    ax2 = ax1.twinx()

    line_actual, = ax2.plot(
        df["date"],
        df["actual_consumption"],
        linestyle="-",
        linewidth=2,
        color="orange",
        label="Actual Consumption",
    )

    line_planned, = ax2.plot(
        df["date"],
        df["planned_consumption"],
        linestyle="--",
        linewidth=2,
        color="green",
        label="Planned Consumption",
    )
    ax2.set_ylabel("Consumption (pantry units)")

    fig.suptitle("Consumption vs Forecast Waste (Next 30 Days)")
    fig.autofmt_xdate()

    # Combined legend
    lines = [line_waste, line_actual, line_planned]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left")

    plt.tight_layout()
    return fig