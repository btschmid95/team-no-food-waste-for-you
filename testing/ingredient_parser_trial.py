# from ingredient_parser import parse_ingredient

# # example ingredients you already have:
# ingredients = [
#     "1 cup TJ’s Traditional Whole Milk Ricotta Cheese",
#     "1 package TJ’s Steamed & Peeled Baby Beets, warmed according to package instructions, if desired, and sliced into thin rounds",
#     "A handful TJ’s Raw Pistachio Nutmeats, roughly chopped",
#     "TJ’s Sea Salt",
#     "TJ’s Black Peppercorns",
#     "Your favorite TJ’s Extra Virgin Olive Oil, for drizzling"
# ]

# for ing in ingredients:
#     result = parse_ingredient(ing)
#     print("Original:", ing)
#     print("Parsed:  ", result.name)
#     print("-" * 40)

# parse_raw_ingredients.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import pandas as pd
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from setup.tables import Base, TJInventory, Recipe, RawIngredient
from ingredient_parser import parse_ingredient


DB_FILE = Path("team-no-food-waste-for-you.sqlite")
OUTPUT_CSV = Path("parsed_raw_ingredients.csv")
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)
Session = sessionmaker(bind=engine)

def parse_all_raw_ingredients(limit=None):
    """
    Pulls all raw ingredients from the database,
    parses them using ingredient-parser, and prints results.
    """
    # session = Session()
    
    # query = session.query(RawIngredient)
    # if limit:
    #     query = query.limit(limit)
    
    # raw_ingredients = query.all()
    
    # for raw in raw_ingredients:
    #     original_text = raw.raw_text
    #     parsed = parse_ingredient(original_text)
    #     print("Original: ", original_text)
    #     print("Parsed:   ", parsed.amount)
    #     print("-" * 50)
    
    # session.close()
    session = Session()
    
    raw_ingredients = session.query(RawIngredient).all()
    
    results = []
    import re
    for raw in raw_ingredients:
        original_text = raw.raw_text
        parsed = parse_ingredient(original_text)

        # Name and confidence
        if parsed.name:
            name_text = " ".join([n.text for n in parsed.name])
            name_conf = sum([n.confidence for n in parsed.name]) / len(parsed.name)
            # Remove TJ's
            name_text = re.sub(r"(tj[’']s|trader\s*joe[’']s)\s*", "", name_text, flags=re.IGNORECASE)
        else:
            name_text = None
            name_conf = None

        # Amount
        amount_value = None
        amount_text = None
        unit_text = None
        amount_conf = None

        if parsed.amount and len(parsed.amount) > 0:
            amt_obj = parsed.amount[0]
            if hasattr(amt_obj, "amounts"):  # CompositeIngredientAmount
                first_part = amt_obj.amounts[0] if amt_obj.amounts else None
                if first_part:
                    try:
                        amount_value = float(first_part.quantity)
                    except (TypeError, ValueError):
                        amount_value = None
                    amount_text = first_part.text
                    unit_text = str(first_part.unit) if first_part.unit else None
                    amount_conf = first_part.confidence
            else:  # single IngredientAmount
                try:
                    amount_value = float(amt_obj.quantity)
                except (TypeError, ValueError):
                    amount_value = None
                amount_text = amt_obj.text
                unit_text = str(amt_obj.unit) if amt_obj.unit else None
                amount_conf = amt_obj.confidence

        # Preparation
        preparation_text = parsed.preparation.text if parsed.preparation else None
        preparation_conf = parsed.preparation.confidence if parsed.preparation else None

        parsed_row = {
            "original_text": original_text,
            "name": name_text,
            "name_confidence": name_conf,
            "amount": amount_value,
            "amount_text": amount_text,
            "unit": unit_text,
            "amount_confidence": amount_conf,
            "preparation": preparation_text,
            "preparation_confidence": preparation_conf
        }

        results.append(parsed_row)

    session.close()
    
    df = pd.DataFrame(results)
    #df = df.drop_duplicates(subset=["name"]).reset_index(drop=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved parsed ingredients to {OUTPUT_CSV}")

if __name__ == "__main__":
    parse_all_raw_ingredients(limit=10)