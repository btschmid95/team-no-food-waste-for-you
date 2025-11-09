from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import pandas as pd
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from data.pipeline.ingredient_category_classifier import predict_category
from setup.tables import Base, TJInventory, Recipe, RawIngredient
from ingredient_parser import parse_ingredient

DB_FILE = Path("team-no-food-waste-for-you.sqlite")
OUTPUT_CSV = Path("parsed_raw_ingredients_no_duplicates.csv")
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)
Session = sessionmaker(bind=engine)

def parse_all_raw_ingredients(limit=None):
    """
    Pulls all raw ingredients from the database, parses them, and predicts top 3 sub-categories
    along with their main categories.
    """
    session = Session()
    raw_ingredients = session.query(RawIngredient).limit(limit).all() if limit else session.query(RawIngredient).all()

    results = []

    for raw in raw_ingredients:
        original_text = raw.raw_text
        parsed = parse_ingredient(original_text)

        # ---- Name & Confidence ----
        if parsed.name:
            name_text = " ".join([n.text for n in parsed.name])
            name_conf = sum([n.confidence for n in parsed.name]) / len(parsed.name)
            # Remove TJ's branding
            name_text = re.sub(r"(tj[’']s|trader\s*joe[’']s)\s*", "", name_text, flags=re.IGNORECASE)
        else:
            name_text = None
            name_conf = None

        # ---- Amount ----
        amount_value = amount_text = unit_text = amount_conf = None
        if parsed.amount and len(parsed.amount) > 0:
            amt_obj = parsed.amount[0]
            if hasattr(amt_obj, "amounts"):
                first_part = amt_obj.amounts[0] if amt_obj.amounts else None
                if first_part:
                    try: amount_value = float(first_part.quantity)
                    except (TypeError, ValueError): amount_value = None
                    amount_text = first_part.text
                    unit_text = str(first_part.unit) if first_part.unit else None
                    amount_conf = first_part.confidence
            else:
                try: amount_value = float(amt_obj.quantity)
                except (TypeError, ValueError): amount_value = None
                amount_text = amt_obj.text
                unit_text = str(amt_obj.unit) if amt_obj.unit else None
                amount_conf = amt_obj.confidence

        # ---- Preparation ----
        preparation_text = parsed.preparation.text if parsed.preparation else None
        preparation_conf = parsed.preparation.confidence if parsed.preparation else None

        # ---- Predict top 3 sub-categories & main categories ----
        if name_text:
            preds = predict_category(name_text)  # Returns [(sub_category, score, main_category), ...]
            # Fill top 3
            top_preds = preds[:3]
        else:
            top_preds = [(None, None, None)] * 3

        # Unpack predictions
        parsed_row = {
            "original_text": original_text,
            "name": name_text,
            "name_confidence": name_conf,
            "amount": amount_value,
            "amount_text": amount_text,
            "unit": unit_text,
            "amount_confidence": amount_conf,
            "preparation": preparation_text,
            "preparation_confidence": preparation_conf,
            # Sub-category & main category predictions
            "likely_sub_category_1": top_preds[0][0],
            "likely_sub_category_1_score": top_preds[0][1],
            "main_category_1": top_preds[0][2],
            "likely_sub_category_2": top_preds[1][0],
            "likely_sub_category_2_score": top_preds[1][1],
            "main_category_2": top_preds[1][2],
            "likely_sub_category_3": top_preds[2][0],
            "likely_sub_category_3_score": top_preds[2][1],
            "main_category_3": top_preds[2][2],
        }

        results.append(parsed_row)

    session.close()

    df = pd.DataFrame(results)
    df = df.drop_duplicates(subset=["name"]).reset_index(drop=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Saved parsed ingredients to {OUTPUT_CSV}")


if __name__ == "__main__":
    parse_all_raw_ingredients(None)
