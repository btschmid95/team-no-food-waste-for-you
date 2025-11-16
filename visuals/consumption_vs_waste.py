import pandas as pd
import matplotlib.pyplot as plt


def get_forecast_waste_by_date(pantry_df):
    """
    From pantry_df, compute how much is expiring each day.
    """
    df = pantry_df.copy()
    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")

    df = df[df["expiration_date"].notna()]

    daily = (
        df.groupby("expiration_date", as_index=False)["amount"]
          .sum()
          .rename(columns={"expiration_date": "date", "amount": "forecast_waste"})
    )
    return daily


def get_planned_consumption_by_date(engine):
    """
    Use recipe_selected + cookbook tables to compute how much
    is planned to be consumed each day.
    """
    # Which recipes were selected, and when
    selected = pd.read_sql("SELECT * FROM recipe_selected;", engine)
    selected["date"] = pd.to_datetime(selected["sel_ts"]).dt.date

    # Ingredient amounts per recipe
    cookbook = pd.read_sql("SELECT * FROM cookbook;", engine)

    # Join recipe selections with their ingredient amounts
    df = selected.merge(cookbook, on="recipe_id", how="left")

    df["date"] = pd.to_datetime(df["date"])

    daily = (
        df.groupby("date", as_index=False)["amount"]
          .sum()
          .rename(columns={"amount": "planned_consumption"})
    )
    return daily


def plot_consumption_vs_waste(pantry_df, engine):
    """
    Visual 2: Dual-axis line chart:
    Variables: Consumption via Recipe at X time, Waste, vs. Time
    """
    # Left axis: forecast waste from pantry
    forecast_df = get_forecast_waste_by_date(pantry_df)

    # Right axis: planned consumption from recipe schedule
    cons_df = get_planned_consumption_by_date(engine)

    # Combine on date
    df = pd.merge(forecast_df, cons_df, on="date", how="outer").sort_values("date")
    df["forecast_waste"] = df["forecast_waste"].fillna(0)
    df["planned_consumption"] = df["planned_consumption"].fillna(0)

    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Left axis: forecast waste
    ax1.plot(df["date"], df["forecast_waste"], label="Forecast Waste", linewidth=2)
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Forecast Waste")

    # Right axis: planned consumption
    ax2 = ax1.twinx()
    ax2.plot(
        df["date"],
        df["planned_consumption"],
        linestyle="--",
        label="Planned Consumption",
        linewidth=2,
        color="orange",
    )
    ax2.set_ylabel("Planned Consumption")

    fig.suptitle("Planned Consumption vs Forecast Waste")
    fig.autofmt_xdate()

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.tight_layout()
    return fig