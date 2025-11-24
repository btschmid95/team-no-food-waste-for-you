import pandas as pd
import sys
from pathlib import Path

# Allow pipeline scripts to import database + services
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.config import DATABASE_URL
from sqlalchemy.orm import Session
from database.tables import Ingredient, TJInventory

FIRST_UNITS = {
    "cup": 8, "cups": 8,
    "tablespoon": 0.5, "tablespoons": 0.5,
    "Tbsp": 0.5,
    "teaspoon": 0.1667, "teaspoons": 0.1667,
    "ounce": 1, "ounces": 1,
    "oz": 1, "Oz": 1
}

DOES_NOT_WORK = {
    "slice", "slices", "clove", "cloves",
    "handful", "sprig", "sprigs",
    "loaf", "pound", "scoops", "bar",
    "pint", "heads", "egg","eggs"
}

PKG_KEYWORDS = {
    "pkg", "pkg.", "pkgs", "package", "packages"
}

CONTAINER_UNITS = {
    "box", "boxes",
    "package", "packages",
    "bag", "bags",
    "container",
    "jar", "jars",
    "tub",
    "pack",
    "carton",
    "sheet", "sheets",
    "package", "packages"
}

def convert_units_for_all_ingredients(session: Session):
    """
    Convert all Ingredient.amount/unit into pantry_amount/pantry_unit
    using matched_product_id and store units.
    """
    ingredients = (
        session.query(Ingredient)
        .outerjoin(TJInventory, Ingredient.matched_product_id == TJInventory.product_id)
        .add_entity(TJInventory)
        .all()
    )

    updated_count = 0

    for ing, prod in ingredients:
        raw_text = (ing.raw_text or "").lower().strip()
        raw_contains_pkg = any(k in raw_text for k in PKG_KEYWORDS)

        if (ing.unit is None or ing.unit.strip() == "") and raw_contains_pkg:
            ing.unit = "package"

        if ing.unit in FIRST_UNITS:
            ing.pantry_amount = ing.amount * FIRST_UNITS[ing.unit]
            ing.pantry_unit = "oz"
            updated_count += 1
            continue

        if ing.unit in DOES_NOT_WORK:
            ing.pantry_amount = ing.amount
            ing.pantry_unit = ing.unit
            continue

        if (
            prod is not None 
            and prod.quantity is not None 
            and ing.amount is not None
        ):

            if not ing.unit or ing.unit.strip() == "":
                ing.pantry_amount = ing.amount
                ing.pantry_unit = "count"
                updated_count += 1
                continue

            if ing.unit in CONTAINER_UNITS:
                ing.pantry_amount = ing.amount * prod.quantity
                ing.pantry_unit = prod.unit
                updated_count += 1

            ing.pantry_amount = ing.amount * prod.quantity
            ing.pantry_unit = prod.unit
            updated_count += 1
            continue

        ing.pantry_amount = ing.amount
        ing.pantry_unit = ing.unit

    session.commit()
    return updated_count

def run_unit_conversion():
    """
    Final pipeline step:
    Convert all Ingredient.amount/unit into normalized pantry_amount/pantry_unit.
    Uses Ingredient.matched_product_id + TJInventory data.
    """
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Converting ingredient units into normalized pantry units.")
    updated = convert_units_for_all_ingredients(session)

    print(f"Completed unit conversion. {updated} ingredients updated.")


if __name__ == "__main__":
    run_unit_conversion()

