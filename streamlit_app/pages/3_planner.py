import streamlit as st
import pandas as pd
import sys
from pathlib import Path
import ast

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Add the data folder to sys.path so you can import the pipeline
sys.path.append(str(PROJECT_ROOT / 'data'))

from recipe_ingredient_product_pipeline import normalize_text, process_ingredients
st.set_page_config(layout="wide", page_title="Recipe Ingredient Mapping")
st.title("Recipe Ingredient Mapping")


products_file = PROJECT_ROOT / "data/trader_joes_products_v2.csv"
recipes_file = PROJECT_ROOT / "data/trader_joes_recipes.csv"

products_df = pd.read_csv(products_file)
recipes_df = pd.read_csv(recipes_file)
recipes_df['ingredients_list'] = recipes_df['ingredients'].apply(ast.literal_eval)
product_names = products_df['product_name'].tolist()
normalized_products = [normalize_text(p) for p in product_names]


# Process ingredients
recipes_df = process_ingredients(recipes_df, 'ingredients_list', normalized_products)

# Select a recipe
recipe_selection = st.selectbox("Select a recipe", recipes_df['title'].tolist())
selected_recipe = recipes_df[recipes_df['title'] == recipe_selection].iloc[0]

st.subheader("Mapped Ingredients")
for orig, match in zip(selected_recipe['ingredients_list'], selected_recipe['matched_product']):
    st.write(f"{orig}  →  {match}")
