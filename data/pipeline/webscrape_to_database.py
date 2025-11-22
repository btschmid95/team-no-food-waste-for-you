import pandas as pd
import ast
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.tables import Base, TJInventory, Recipe, Ingredient
from database.config import DATABASE_URL
import re

try:
    from web_scraper import run_web_scraper
except:
    run_web_scraper = None

DATA_DIR = Path("data")
PRODUCTS_XLSX = DATA_DIR / "trader_joes_products_v3_with_shelf_life.xlsx"
RECIPES_CSV = DATA_DIR / "trader_joes_recipes.csv"

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


def parse_price(p):
    if pd.isna(p):
        return None
    if isinstance(p, (int, float)):
        return float(p)

    s = str(p).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_size_string(size):
    """
    Parse a size string like '/16 Oz', '/1 Each', '32 oz', '18.3 Oz'.
    Returns (quantity: float or None, unit: str or None)
    """
    if not size or pd.isna(size):
        return None, None
    
    # remove leading slash
    size = str(size).strip().lstrip("/")
    
    # extract: number (int or float) + unit text
    match = re.match(r"([0-9]*\.?[0-9]+)\s*(.*)", size)
    if not match:
        return None, size  # weird case – return unit only
    
    quantity = float(match.group(1))
    unit = match.group(2).strip() if match.group(2) else None
    
    return quantity, unit


def convert_shelf_life(days_value, unit):
    """Normalize shelf life to days."""
    if pd.isna(days_value):
        return None

    try:
        val = float(days_value)
    except:
        return None

    if not unit:
        return int(val)

    u = str(unit).lower().strip()

    if "day" in u:
        return int(val)
    if "week" in u:
        return int(val * 7)
    if "month" in u:
        return int(val * 30)

    return int(val)


def load_data():
    """Try scraper → fallback to CSV/XLSX."""
    if run_web_scraper:
        try:
            recipe_df, products_df = run_web_scraper()
            print("Scraping successful!")
            return recipe_df, products_df
        except Exception as e:
            print(f"Scraping failed: {e}")

    if not RECIPES_CSV.exists() or not PRODUCTS_XLSX.exists():
        raise FileNotFoundError("No scraped data or local data files found.")

    recipe_df = pd.read_csv(RECIPES_CSV)
    products_df = pd.read_excel(PRODUCTS_XLSX)

    print("Loaded Excel/CSV fallback data from /data directory.")
    return recipe_df, products_df

def populate_database(recipe_df, products_df):
    session = Session()

    # 1. Insert PRODUCTS
    for _, row in products_df.iterrows():
        product_name = row.get("product_name")

        if session.query(TJInventory).filter_by(name=product_name).first():
            continue

        raw_unit = row.get("unit")
        quantity, clean_unit = parse_size_string(raw_unit)

        product = TJInventory(
            name=product_name,
            norm_name=product_name.lower() if product_name else None,
            unit=clean_unit,
            quantity=quantity,
            price=parse_price(row.get("price")),
            url=row.get("url"),
            category=row.get("category"),
            sub_category=row.get("sub_category"),
            shelf_life_days=convert_shelf_life(
                row.get("shelf_life"), row.get("shelf_life_unit")
            ),
        )


        session.add(product)

    # 2. Insert RECIPES + RAW INGREDIENTS
    for _, row in recipe_df.iterrows():
        title = row.get("title")

        if session.query(Recipe).filter_by(title=title).first():
            continue

        # Create recipe
        recipe = Recipe(
            title=title,
            category=row.get("category"),
            url=row.get("url"),
            image_url=row.get("image_url"),
            serves=row.get("serves"),
            time=row.get("time"),
        )

        session.add(recipe)
        session.flush()  # get recipe.recipe_id

        # Load ingredients
        ingredients_list = row.get("ingredients")

        if isinstance(ingredients_list, str):
            try:
                ingredients_list = ast.literal_eval(ingredients_list)
            except:
                ingredients_list = [ingredients_list]

        if not isinstance(ingredients_list, list):
            ingredients_list = [str(ingredients_list)]

        # Insert ingredient rows
        for raw_ing in ingredients_list:
            ingredient = Ingredient(
                recipe_id=recipe.recipe_id,
                raw_text=str(raw_ing).strip(),
                name=None,
                norm_name=None,
                amount=None,
                unit=None,
                matched_product_id=None,
            )

            session.add(ingredient)

    session.commit()
    session.close()
    print("Database populated successfully!")


if __name__ == "__main__":
    recipe_df, products_df = load_data()
    populate_database(recipe_df, products_df)
