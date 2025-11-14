import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.config import DATABASE_URL
from database.tables import (
    Recipe,
    UsableIngredient,
    RecipeIngredient,
    TJInventory,
    IngredientProductMap
)
from database.normalization import normalize

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

DATA_FILE = Path("data/all_ingredients_mapped_to_products_hand-edited_final.xlsx")


def populate_ingredient_mappings():
    session = Session()

    df = pd.read_excel(DATA_FILE)

    for _, row in df.iterrows():
        recipe_title = row["recipe_title"]
        ingredient_name = normalize(str(row["name"]).strip())

        recipe = session.query(Recipe).filter_by(title=recipe_title).first()
        if not recipe:
            print(f"❌ Recipe not found: {recipe_title}")
            continue

        ingredient = session.query(UsableIngredient).filter_by(
            norm_name=ingredient_name
        ).first()

        if not ingredient:
            ingredient = UsableIngredient(
                norm_name=ingredient_name,
                raw_name=row["name"]
            )
            session.add(ingredient)
            session.flush()

        recipe_ing = RecipeIngredient(
            recipe_id=recipe.recipe_id,
            ingredient_id=ingredient.ingredient_id,
            amount=row.get("amount"),
            unit=row.get("unit")
        )
        session.add(recipe_ing)

        matched = row.get("matched_products")

        if pd.isna(matched) or matched == "[]":
            continue

        matched_clean = (
            str(matched)
            .replace("[", "")
            .replace("]", "")
            .split(";")
        )
        matched_clean = [m.strip() for m in matched_clean if m.strip()]

        if not matched_clean:
            continue

        first_match_name = matched_clean[0]

        product = session.query(TJInventory).filter_by(name=first_match_name).first()
        if not product:
            print(f"❌ Product not found in DB: {first_match_name}")
            continue

        mapping = IngredientProductMap(
            ingredient_id=ingredient.ingredient_id,
            product_id=product.product_id,
            ingredient_amount=row.get("amount"),
            ingredient_unit=row.get("unit"),
            product_amount=1,
            product_unit=product.unit,
            is_default=1
        )

        session.add(mapping)

    session.commit()
    session.close()
    print("✅ Mapped ingredients + quantities + product links successfully!")


if __name__ == "__main__":
    populate_ingredient_mappings()
