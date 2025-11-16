import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx

def load_recipe_ingredient_data(engine):
    """
    Load recipes, ingredients, and their relationships from the database.
    """
    recipes = pd.read_sql("SELECT recipe_id, title, category FROM recipe;", engine)
    ingredients = pd.read_sql(
        "SELECT ingredient_id, norm_name FROM usable_ingredients;", engine
    )
    inv_idx = pd.read_sql(
        "SELECT ingredient_id, recipe_id FROM ingredient_recipe_inverted_index;",
        engine,
    )

    return recipes, ingredients, inv_idx


def build_recipe_ingredient_graph(recipes_df, ingredients_df, inv_idx_df):
    """
    Build a NetworkX graph of recipes and ingredients.
    """
    G = nx.Graph()

    # Add recipe nodes
    for _, row in recipes_df.iterrows():
        G.add_node(
            f"recipe_{row['recipe_id']}",
            type="recipe",
            label=row["title"],
            category=row.get("category", None),
        )

    # Add ingredient nodes
    for _, row in ingredients_df.iterrows():
        G.add_node(
            f"ingredient_{row['ingredient_id']}",
            type="ingredient",
            label=row["norm_name"],
        )

    # Add edges between recipes and ingredients
    for _, row in inv_idx_df.iterrows():
        r_node = f"recipe_{row['recipe_id']}"
        i_node = f"ingredient_{row['ingredient_id']}"
        if r_node in G.nodes and i_node in G.nodes:
            G.add_edge(r_node, i_node)

    return G


def plot_recipe_overlap_network(G, sample_n_recipes=30):
    """
    Visual 4:
    Plot a recipe–ingredient overlap network.

    Nodes:
      - Squares = recipes
      - Circles = ingredients
    """
    H = G.copy()

    # Recipe sample (to limit graph output, OPTIONAL)
    recipe_nodes = [n for n, d in H.nodes(data=True) if d.get("type") == "recipe"]
    if sample_n_recipes is not None and len(recipe_nodes) > sample_n_recipes:
        sampled_recipes = set(recipe_nodes[:sample_n_recipes])
        neighbors = set()
        for r in sampled_recipes:
            neighbors.update(H.neighbors(r))
        keep_nodes = sampled_recipes | neighbors
        H = H.subgraph(keep_nodes).copy()

    # Layout
    pos = nx.spring_layout(H, k=0.3, iterations=50)

    recipe_nodes = [n for n, d in H.nodes(data=True) if d.get("type") == "recipe"]
    ingredient_nodes = [n for n, d in H.nodes(data=True) if d.get("type") == "ingredient"]

    # Visualize
    fig, ax = plt.subplots(figsize=(10, 8))

    nx.draw_networkx_nodes(
        H, pos, nodelist=recipe_nodes, node_shape="s", node_size=400, label="Recipes", ax=ax
    )
    nx.draw_networkx_nodes(
        H, pos, nodelist=ingredient_nodes, node_shape="o", node_size=200, alpha=0.6, label="Ingredients", ax=ax
    )
    nx.draw_networkx_edges(H, pos, alpha=0.3, ax=ax)

    # Labels
    labels = {n: d["label"] for n, d in H.nodes(data=True) if d.get("type") == "recipe"}
    nx.draw_networkx_labels(H, pos, labels=labels, font_size=8, ax=ax)

    ax.set_title("Recipe–Ingredient Overlap Network")
    ax.set_axis_off()
    ax.legend()
    fig.tight_layout()
    return fig