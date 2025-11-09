import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from setup.tables import Base, TJInventory, Recipe, RawIngredient

try:
    from web_scraper import run_web_scraper
except:
    pass

DB_FILE = Path("team-no-food-waste-for-you.sqlite")
DATA_DIR = Path("data")

# --- Database setup ---
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)
Session = sessionmaker(bind=engine)

def parse_price(p):
    """Convert price string to float safely."""
    if pd.isna(p):
        return None
    if isinstance(p, (int, float)):
        return float(p)
    s = str(p).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

def load_data():
    """Try to scrape; fall back to CSV if unavailable."""
    try:
        recipe_df, products_df = run_web_scraper()
        print("Scraping successful!")
    except Exception as e:
        print(f"Scraping failed: {e}")
        recipe_csv = DATA_DIR / "trader_joes_recipes.csv"
        products_csv = DATA_DIR / "trader_joes_products_v3.csv"

        if recipe_csv.exists() and products_csv.exists():
            recipe_df = pd.read_csv(recipe_csv)
            products_df = pd.read_csv(products_csv)
            print("Loaded CSV files from /data folder.")
        else:
            raise FileNotFoundError("No scraped data or CSV files found!")

    return recipe_df, products_df

def populate_database(recipe_df, products_df):
    session = Session()

    # --- TJ Inventory ---
    for _, row in products_df.iterrows():
        product_name = row.get("product_name")
        if not session.query(TJInventory).filter_by(name=product_name).first():
            price = parse_price(row.get("price"))
            product = TJInventory(
                name=product_name,
                norm_name=None,
                unit=row.get("unit"),
                price=price,
                url=row.get("url"),
                category=row.get("category"),
                sub_category=row.get("sub_category"),
            )

            session.add(product)

    # --- Recipes ---
    for _, row in recipe_df.iterrows():
        title = row.get("title")
        if not session.query(Recipe).filter_by(title=title).first():
            recipe = Recipe(
                title=title,
                category=row.get("category"),
                url=row.get("url"),
                image_url=row.get("image_url"),
                serves=row.get("serves"),
                time=row.get("time"),
            )
            session.add(recipe)
            session.flush()  # Assign recipe_id for linking ingredients

            # --- Raw ingredients table ---
            ingredients_list = row.get("ingredients")
            if isinstance(ingredients_list, str):
                try:
                    ingredients_list = pd.eval(ingredients_list)  # convert string list to Python list
                except:
                    ingredients_list = [ingredients_list]

            for ing in ingredients_list:
                raw_ing = RawIngredient(
                    recipe_id=recipe.recipe_id,
                    raw_text=ing
                )
                session.add(raw_ing)

    session.commit()
    session.close()
    print("Database populated successfully!")

if __name__ == "__main__":
    recipe_df, products_df = load_data()
    populate_database(recipe_df, products_df)
