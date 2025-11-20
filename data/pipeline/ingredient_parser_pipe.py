import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from database.tables import Ingredient, IngredientParseMeta, Recipe
from database.config import DATABASE_URL
from data.pipeline.ingredient_category_classifier import predict_category
from ingredient_parser import parse_ingredient
from database.normalization import normalize

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

OUTPUT_CSV = Path("data/pipeline/all_ingredients_parsed.csv")

def parse_all_ingredients(limit=None):
    """
    Parse ingredients, store metadata in DB,
    update Ingredient table, and generate CSV for reference.
    """
    session = Session()

    query = session.query(Ingredient, Recipe.title, Recipe.category) \
                   .join(Recipe, Ingredient.recipe_id == Recipe.recipe_id)

    if limit:
        query = query.limit(limit)

    rows = query.all()
    print(f"Parsing {len(rows)} ingredients...")

    csv_rows = []   # <-- Save here for output CSV

    for ing, recipe_title, recipe_category in rows:
        raw_text = ing.raw_text
        parsed = parse_ingredient(raw_text)

        if parsed.name:
            parsed_name = " ".join([n.text for n in parsed.name])
            parsed_name = re.sub(r"(tj['’]s|trader\s*joe['’]s)\s*",
                                "", parsed_name, flags=re.IGNORECASE)
            name_conf = sum([n.confidence for n in parsed.name]) / len(parsed.name)
        else:
            parsed_name = None
            name_conf = None

        norm_name = normalize(parsed_name) if parsed_name else None

        amount_value = None
        unit_text = None
        amount_conf = None

        preparation_text = parsed.preparation.text if parsed.preparation else None
        preparation_conf = parsed.preparation.confidence if parsed.preparation else None

        try:
            if parsed_name:
                preds = predict_category(parsed_name)
                top_preds = preds[:3]
            else:
                top_preds = [(None, None, None)] * 3

        except Exception as e:
            if not hasattr(parse_all_ingredients, "_prediction_error_logged"):
                print("⚠️  WARNING: Category model not available. Skipping category predictions.")
                print(f"⚙️  Details: {e}")
                parse_all_ingredients._prediction_error_logged = True
            top_preds = [(None, None, None)] * 3


        ing.name = parsed_name
        ing.norm_name = norm_name
        ing.amount = amount_value
        ing.unit = unit_text

        meta = IngredientParseMeta(
            ingredient_id=ing.ingredient_id,
            raw_text=raw_text,
            parsed_name=parsed_name,

            amount=amount_value,
            amount_unit=unit_text,

            subcat_1=top_preds[0][0],
            subcat_1_score=top_preds[0][1],
            maincat_1=top_preds[0][2],

            subcat_2=top_preds[1][0],
            subcat_2_score=top_preds[1][1],
            maincat_2=top_preds[1][2],

            subcat_3=top_preds[2][0],
            subcat_3_score=top_preds[2][1],
            maincat_3=top_preds[2][2],

            preparation=preparation_text,
            preparation_confidence=preparation_conf,

            recipe_title=recipe_title,
            recipe_category=recipe_category,
        )

        csv_rows.append({
            "ingredient_id": ing.ingredient_id,
            "original_text": raw_text,
            "name": parsed_name,
            "norm_name": norm_name,
            "name_confidence": name_conf,
            "amount": amount_value,
            "unit": unit_text,
            "amount_confidence": amount_conf,
            "preparation": preparation_text,
            "preparation_confidence": preparation_conf,
            "recipe_title": recipe_title,
            "recipe_category": recipe_category,
            "likely_sub_category_1": top_preds[0][0],
            "likely_sub_category_1_score": top_preds[0][1],
            "main_category_1": top_preds[0][2],
            "likely_sub_category_2": top_preds[1][0],
            "likely_sub_category_2_score": top_preds[1][1],
            "main_category_2": top_preds[1][2],
            "likely_sub_category_3": top_preds[2][0],
            "likely_sub_category_3_score": top_preds[2][1],
            "main_category_3": top_preds[2][2],
        })
        session.add(meta)

    session.commit()
    session.close()

    print("✅ All ingredients parsed and metadata saved to DB.")

    df = pd.DataFrame(csv_rows)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"CSV saved to: {OUTPUT_CSV}")
    print("All ingredients parsed + stored in DB + exported.")

if __name__ == "__main__":
    parse_all_ingredients()
