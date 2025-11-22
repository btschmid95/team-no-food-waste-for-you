import sys
from pathlib import Path
import pandas as pd

# Make repo root importable
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
import matplotlib.pyplot as plt
from services.recipe_manager import RecipeManager

def plot_consumption_vs_waste(engine):
    """
    Visual 2: Dual-axis line chart:
    Variables: Consumption via Recipe at X time, Waste, vs. Time
    """
    from visuals.pantry_analytics import (
        get_forecast_waste_by_date,
        load_pantry_with_category
    )

    # Load pantry from DB
    pantry_df = load_pantry_with_category(engine)

    # Left axis: forecast waste
    forecast_df = get_forecast_waste_by_date(pantry_df)

    # Right axis: planned consumption (from recipes)
    cons_df = RecipeManager.get_planned_consumption_by_date()

    # Merge timelines
    df = pd.merge(forecast_df, cons_df, on="date", how="outer").sort_values("date")
    df["forecast_waste"] = df["forecast_waste"].fillna(0)
    df["planned_consumption"] = df["planned_consumption"].fillna(0)

    fig, ax1 = plt.subplots(figsize=(10, 5))

    ax1.plot(df["date"], df["forecast_waste"], label="Forecast Waste", linewidth=2)
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Forecast Waste")

    ax2 = ax1.twinx()
    ax2.plot(df["date"], df["planned_consumption"],
             linestyle="--", linewidth=2, color="orange",
             label="Planned Consumption")
    ax2.set_ylabel("Planned Consumption")

    fig.suptitle("Planned Consumption vs Forecast Waste")
    fig.autofmt_xdate()

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.tight_layout()
    return fig
