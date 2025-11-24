import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from database.config import DATABASE_URL
from database.tables import (
    Ingredient,
    IngredientParseMeta,
    Recipe,
    TJInventory,
    Base
)
from data.pipeline.map_to_product_with_context import map_to_product_top_n_sub_main_expanded

OUTPUT_CSV = PROJECT_ROOT / "data" /"pipeline" / "ingredient_product_matches.csv"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)

TOP_N = 3

def run_mapping_pipeline():
    session = SessionLocal()


    print("📦 Loading database ingredients + metadata…")

    ingredients = (
        session.query(Ingredient)
        .options(
            joinedload(Ingredient.parse_meta),
            joinedload(Ingredient.recipe)
        )
        .all()
    )

    products = session.query(TJInventory).all()

    ing_records = []

    for ing in ingredients:
        meta = ing.parse_meta[0] if ing.parse_meta else None

        ing_records.append({
            "ingredient_id": ing.ingredient_id,
            "name": meta.parsed_name if meta else None,
            "recipe_title": ing.recipe.title if ing.recipe else None,
            "recipe_category": ing.recipe.category if ing.recipe else None,

            "likely_sub_category_1": meta.subcat_1 if meta else None,
            "likely_sub_category_1_score": meta.subcat_1_score if meta else None,
            "main_category_1": meta.maincat_1 if meta else None,

            "likely_sub_category_2": meta.subcat_2 if meta else None,
            "likely_sub_category_2_score": meta.subcat_2_score if meta else None,
            "main_category_2": meta.maincat_2 if meta else None,

            "likely_sub_category_3": meta.subcat_3 if meta else None,
            "likely_sub_category_3_score": meta.subcat_3_score if meta else None,
            "main_category_3": meta.maincat_3 if meta else None,
        })

    ing_df = pd.DataFrame(ing_records)

    prod_df = pd.DataFrame([{
        "product_id": p.product_id,
        "product_name": p.name,
        "unit": p.unit,
        "category": p.category,
        "sub_category": p.sub_category
    } for p in products])

    print("🔍 Running exact matching logic…")
    mapped_df = ing_df.copy()
    map_to_product_top_n_sub_main_expanded(
        mapped_df,
        prod_df,
        output_path=OUTPUT_CSV,
        top_n=TOP_N
    )

    print(f"CSV written → {OUTPUT_CSV}")
    print("Updating DB with top-1 matches...")

    for _, row in mapped_df.iterrows():
        ingredient_id = row["ingredient_id"]
        ingredient = session.query(Ingredient).get(ingredient_id)

        if pd.isna(row["matched_products"]):
            continue

        first_product_name = row["matched_products"].split("; ")[0]

        product = session.query(TJInventory).filter(
            TJInventory.name == first_product_name
        ).first()

        if product:
            ingredient.matched_product_id = product.product_id

    session.commit()
    session.close()

    print("Finished mapping + DB update")

if __name__ == "__main__":
    run_mapping_pipeline()
