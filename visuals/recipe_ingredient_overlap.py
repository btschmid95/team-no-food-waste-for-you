import sys
from pathlib import Path
import pandas as pd

# Make repo root importable
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
import matplotlib.pyplot as plt
import networkx as nx
from visuals.pantry_analytics import load_recipe_product_data

def build_recipe_product_graph(recipes_df, products_df, recipe_ing_map):
    """
    Build a graph where:
      - Recipe nodes connect to Product nodes
    """
    G = nx.Graph()

    # Add recipe nodes
    for _, r in recipes_df.iterrows():
        G.add_node(
            f"recipe_{r.recipe_id}",
            type="recipe",
            label=r.title,
            category=r.category
        )

    # Add product nodes
    for _, p in products_df.iterrows():
        G.add_node(
            f"product_{p.product_id}",
            type="product",
            label=p.name,
            category=p.category
        )

    # Add edges: recipe → product
    for _, row in recipe_ing_map.iterrows():
        rec = f"recipe_{row.recipe_id}"
        prod = f"product_{row.matched_product_id}"

        if rec in G.nodes and prod in G.nodes:
            G.add_edge(rec, prod)

    return G


def plot_recipe_overlap_network(G, sample_n_recipes=30):
    """
    Plot a recipe–product overlap network (Visual 4).

    Nodes:
      - Squares = recipes
      - Circles = products
    """
    H = G.copy()

    # Optionally limit to a sample of recipes
    recipe_nodes = [n for n, d in H.nodes(data=True) if d.get("type") == "recipe"]

    if sample_n_recipes is not None and len(recipe_nodes) > sample_n_recipes:
        sampled = set(recipe_nodes[:sample_n_recipes])
        neighbors = set()
        for r in sampled:
            neighbors.update(H.neighbors(r))
        keep = sampled | neighbors
        H = H.subgraph(keep).copy()

    # Layout
    pos = nx.spring_layout(H, k=0.3, iterations=50)

    recipe_nodes = [n for n, d in H.nodes(data=True) if d.get("type") == "recipe"]
    product_nodes = [n for n, d in H.nodes(data=True) if d.get("type") == "product"]

    # Plot
    fig, ax = plt.subplots(figsize=(12, 9))

    nx.draw_networkx_nodes(
        H, pos, nodelist=recipe_nodes, node_shape="s",
        node_size=450, label="Recipes", ax=ax
    )
    nx.draw_networkx_nodes(
        H, pos, nodelist=product_nodes, node_shape="o",
        node_size=250, alpha=0.7, label="Products", ax=ax
    )

    nx.draw_networkx_edges(H, pos, alpha=0.3, ax=ax)

    # Label only recipe nodes (products get messy)
    labels = {n: d["label"] for n, d in H.nodes(data=True)
              if d.get("type") == "recipe"}

    nx.draw_networkx_labels(H, pos, labels=labels, font_size=8, ax=ax)

    ax.set_title("Recipe–Product Overlap Network")
    ax.set_axis_off()
    ax.legend()
    fig.tight_layout()

    return fig
