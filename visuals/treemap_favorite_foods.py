import plotly.express as px

def plot_consumption_treemap(engine):
    from visuals.pantry_analytics import (
        compute_consumption_by_category,
        create_treemap_dataframe
    )

    cons = compute_consumption_by_category(engine)
    df = create_treemap_dataframe(cons)

    if df.empty:
        return None
    df["display_label"] = (df["product"])
    df["customdata"] = df["unit"]
    fig = px.treemap(
        df,
        path=["ROOT", "All Food", "display_label"],
        values="value",
        color="All Food",
        custom_data=["unit"],   # <-- THIS IS THE FIX
        color_discrete_sequence=px.colors.qualitative.Set3,
        title="Consumption Breakdown by Category & Product"
    )
        # Root node not drawn
    fig.update_traces(root_color="rgba(0,0,0,0)")

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Consumed: %{value} %{customdata[0]}<extra></extra>"
    )
    fig.update_traces(
        texttemplate=(
            "%{label}<br>"
            "<span style='font-size:10px; opacity:0.8;'>"
            "%{value} %{customdata[0]} consumed"
            "</span>"
        ),
        textinfo="label+text"
    )
    return fig
