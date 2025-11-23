# Import
import pandas as pd
import re
import ast
from sqlalchemy import create_engine, text
from data.ingredient_normalization import normalize

recipes = pd.read_csv("../data/trader_joes_recipes.csv")
tj_inventory = pd.read_csv("../data/trader_joes_products_v3.csv")

# creating TJ inventory
def parse_price_to_float(p):
    """Convert price strings like '$3.99' or 3.99 to floats safely."""
    if pd.isna(p):
        return None
    if isinstance(p, (int, float)):
        return float(p)
    s = str(p).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

tj = pd.DataFrame({
    "name":  tj_inventory["product_name"],
    "unit":  tj_inventory["unit"],
    "price": tj_inventory["price"].map(parse_price_to_float) if "price" in tj_inventory.columns else None,
    "url":   tj_inventory["url"],
    "category": tj_inventory["category"],
})
tj["norm_name"]=tj["name"].apply(lambda x: normalize(x) if isinstance(x, str) else x)
tj = tj.drop_duplicates(subset=["name", "unit", "price"]).reset_index(drop=True)
tj["product_id"] = tj.index + 1
tj = tj[["product_id", "name", "norm_name", "unit", "price", "url", "category"]]

# Helper function to normalize recipes
recipes["ingredients"] = recipes["ingredients"].apply(
    lambda x: ast.literal_eval(x) if isinstance(x, str) else x
)

def split_ingredient(text):
    """
    Split strings like '4 tablespoons TJ’s Salted Butter' into:
    quantity = '4 tablespoons', ingredient = "TJ’s Salted Butter"
    """

    match = re.match(r"^([\d¼½¾⅓⅔⅛⅜⅝⅞\s\-–/]+[a-zA-Z]*)\s+(.*)", text)
    if match:
        qty = match.group(1).strip()
        name = match.group(2).strip()
    else:
        qty, name = None, text.strip()
    return pd.Series([qty, name])

# Explode recipes so each row = 1 ingredient per recipe
recipes_exploded = recipes.explode("ingredients", ignore_index=True)
recipes_exploded[["quantity_text", "ingredient_name"]] = recipes_exploded["ingredients"].apply(split_ingredient)

cookbook_df = recipes_exploded[["title", "category", "ingredient_name", "quantity_text", 'url', 'image_url', 'serves', 'time']]
cookbook_df["name"] = cookbook_df["ingredient_name"].apply(lambda x: normalize(x) if isinstance(x, str) else x)
cookbook_df.drop(columns=["ingredient_name"], inplace=True)
possible_ingredients = cookbook_df['name'].unique()
usable_ingredients = pd.DataFrame(possible_ingredients, columns=["Ingredient"])

# creating database
engine = create_engine("sqlite:///cookbook.db", echo=False)

schema_sql = """
PRAGMA foreign_keys = ON;
--Cookbook
CREATE TABLE IF NOT EXISTS recipe(
  recipe_id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT,
  image_url TEXT,
  serves TEXT,
  time TEXT,
  category TEXT
);

CREATE TABLE IF NOT EXISTS usable_ingredients(
  ingredient_id INTEGER PRIMARY KEY,
  raw_name TEXT,
  norm_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quantity(
  quantity_id INTEGER PRIMARY KEY,
  amount_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cookbook(
  recipe_id INTEGER NOT NULL,
  ingredient_id INTEGER NOT NULL,
  amount REAL,            -- numeric quantity (nullable)
  unit   TEXT,            -- unit text (nullable)
  PRIMARY KEY (recipe_id, ingredient_id),
  FOREIGN KEY (recipe_id) REFERENCES recipe(recipe_id) ON DELETE CASCADE,
  FOREIGN KEY (ingredient_id) REFERENCES usable_ingredients(ingredient_id) ON DELETE CASCADE
);

-- Pantry
CREATE TABLE shelf_life (
  ingredient_id INTEGER PRIMARY KEY,
  shelf_life_days INTEGER NOT NULL,
  FOREIGN KEY (ingredient_id) REFERENCES usable_ingredients(ingredient_id)
);

CREATE TABLE pantry (
  pantry_id INTEGER PRIMARY KEY,
  ingredient_id INTEGER NOT NULL,
  amount REAL,
  unit TEXT,
  date_purchased TEXT,    -- stored right here
  expiration_date TEXT,   -- stored right here
  FOREIGN KEY (ingredient_id) REFERENCES usable_ingredients(ingredient_id)
);

-- TJs Inventory
CREATE TABLE IF NOT EXISTS tj_inventory (
  product_id   INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  norm_name    TEXT,           -- normalized name to match usable_ingredients
  amount       REAL,
  unit         TEXT,           -- package size text from CSV (e.g., '/1 Each', '/16 Oz')
  price        REAL,           -- numeric price (e.g., 3.99)
  url          TEXT,           -- if present in CSV
  category     TEXT            -- 'speciality' | 'produce' | 'meat'
);

-- Many-to-many: which product can satisfy which normalized ingredient
CREATE TABLE IF NOT EXISTS sold_as (
  product_id    INTEGER NOT NULL,
  ingredient_id INTEGER NOT NULL,
  PRIMARY KEY (product_id, ingredient_id),
  FOREIGN KEY (product_id)    REFERENCES tj_inventory(product_id),
  FOREIGN KEY (ingredient_id) REFERENCES usable_ingredients(ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_tj_normname ON tj_inventory(norm_name);
CREATE INDEX IF NOT EXISTS idx_soldas_ing   ON sold_as(ingredient_id);

-- Inverted Name
CREATE TABLE IF NOT EXISTS ingredient_recipe_inverted_index (
    ingredient_id INTEGER,
    recipe_id     INTEGER
);

-- Recipe Recommended
CREATE TABLE IF NOT EXISTS recipe_recommended (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER,
    date      TEXT,
    recipe    TEXT
);

-- Recipe Selected
CREATE TABLE IF NOT EXISTS recipe_selected (
    sel_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER,
    sel_ts    TEXT DEFAULT (datetime('now'))
);
"""

conn = engine.raw_connection()
try:
    cur = conn.cursor()
    cur.executescript(schema_sql)
    conn.commit()
finally:
    conn.close()


# filling database
# Recipe table
recipe_df = (
    cookbook_df[["title", "category", "url", "image_url", "serves", "time"]]
    .drop_duplicates()
    .reset_index(drop=True)
)
recipe_df["recipe_id"] = recipe_df.index + 1

# Usable Ingredients table (from recipes)
ingredient_df = (
    cookbook_df[["name"]]  # ingredient column
    .rename(columns={"name": "raw_name"})
    .assign(norm_name=lambda d: d["raw_name"].str.lower().str.strip())
    .drop_duplicates(subset=["norm_name"])
    .reset_index(drop=True)
)
ingredient_df["ingredient_id"] = ingredient_df.index + 1

# Quantity table
quantity_df = (
    cookbook_df[["quantity_text"]]
    .rename(columns={"quantity_text": "amount_text"})
    .dropna()
    .drop_duplicates()
    .reset_index(drop=True)
)
quantity_df["quantity_id"] = quantity_df.index + 1

# Cookbook table
link_df = (
    cookbook_df
    .merge(recipe_df, on=["title", "category", "url", "image_url", "serves", "time"])
    .merge(ingredient_df, left_on=cookbook_df["name"].str.lower().str.strip(), right_on="norm_name")
    .merge(quantity_df, left_on="quantity_text", right_on="amount_text", how="left")
    [["recipe_id", "ingredient_id", "quantity_id"]]
    .drop_duplicates()
    .reset_index(drop=True)
)

# Upload everything to Database
# recipe_df.to_sql("recipe", engine, if_exists="append", index=False)
# ingredient_df.to_sql("usable_ingredients", engine, if_exists="append", index=False)
# quantity_df.to_sql("quantity", engine, if_exists="append", index=False)
# link_df.to_sql("cookbook", engine, if_exists="append", index=False)
# tj.to_sql("tj_inventory", con=engine, if_exists="append", index=False)

