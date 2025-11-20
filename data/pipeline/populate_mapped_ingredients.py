import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.config import DATABASE_URL
from database.tables import Recipe, Ingredient, TJInventory

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

DATA_FILE = Path("data/all_ingredients_mapped_to_products_hand-edited_final.xlsx")


def populate_ingredient_mappings():
    session = Session()
    df = pd.read_excel(DATA_FILE)

    for _, row in df.iterrows():

        recipe_title = str(row["recipe_title"]).strip()
        raw_text = str(row["original_text"]).strip()  # matches Ingredient.raw_text

        # --- 1. Find recipe ---
        recipe = session.query(Recipe).filter_by(title=recipe_title).first()
        if not recipe:
            print(f"❌ Recipe not found: {recipe_title}")
            continue

        # --- 2. Find ingredient by exact raw_text match ---
        ingredient = (
            session.query(Ingredient)
            .filter_by(recipe_id=recipe.recipe_id, raw_text=raw_text)
            .first()
        )

        if not ingredient:
            print(f"❌ Ingredient not found: '{raw_text}' (recipe: {recipe_title})")
            continue

        # --- 3. Update amount/unit from hand-edited file (optional) ---
        amt = row.get("amount")
        unit = row.get("unit")

        if pd.notna(amt):
            ingredient.amount = amt

        if pd.notna(unit):
            ingredient.unit = unit

        # --- 4. Extract matched products ---
        matched = row.get("matched_products")
        if pd.isna(matched) or matched == "[]":
            continue

        matched_list = (
            str(matched).replace("[", "").replace("]", "").split(";")
        )
        matched_list = [m.strip() for m in matched_list if m.strip()]

        if not matched_list:
            continue

        # Only use the first match
        product_name = matched_list[0]

        # --- 5. Look up product ---
        product = session.query(TJInventory).filter_by(name=product_name).first()
        if not product:
            print(f"❌ Product not found in TJInventory: {product_name}")
            continue

        ingredient.matched_product_id = product.product_id

    session.commit()
    session.close()
    print("✅ Ingredient → Product mappings updated successfully!")


if __name__ == "__main__":
    populate_ingredient_mappings()
