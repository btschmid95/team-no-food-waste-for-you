# Import
import re
import pandas as pd
from sqlalchemy import create_engine, text

recipes_csv = "../web_scraper/trader_joes_recipes.csv"
products_csv = "../web_scraper/trader_joes_products.csv"
fruitveg_csv = "../web_scraper/traderjoes_fresh-fruits-veggies_products.csv"
meat_csv = "../web_scraper/traderjoes_meat_products.csv"

# if you already built this, just assign it:
# normalized_df = <your DataFrame with columns: ingredient_id, ingredient_name, norm_name>

# --- helper: simple normalizer to line up TJ product names with norm_name ---
def normalize_name(s: str) -> str:
    if pd.isna(s):
        return None
    s = s.lower()
    s = re.sub(r"tj[’']s\s+", "", s)                 # drop “TJ’s ”
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)             # kill punctuation
    s = re.sub(r"\s+", " ", s).strip()
    # remove common descriptors after commas like ", rinsed", ", sliced"
    s = s.split(",")[0].strip()
    return s

# --- load CSVs into staging DataFrames ---
recipes_raw = pd.read_csv(recipes_csv)
products = pd.read_csv(products_csv)
fruit_veg = pd.read_csv(fruitveg_csv)
meat = pd.read_csv(meat_csv)

# Optional: ensure minimal expected columns
# recipes_raw expected columns (example): title, url, image_url, serves, time, ingredient_name, quantity_text
# If your recipes CSV is split into recipe header + ingredients, merge before continuing.

# --- if you already have normalized_ingredients (2nd image) as a CSV or DF, use it here ---
# For demo: build from recipes_raw if needed
if not {"ingredient_id","ingredient_name","norm_name"}.issubset(recipes_raw.columns):
    # derive one from ingredient lines in recipes
    if "ingredient_name" not in recipes_raw.columns:
        raise ValueError("recipes CSV must include an 'ingredient_name' column or provide normalized_ingredients.")
    tmp = (recipes_raw[["ingredient_name"]]
           .dropna().drop_duplicates().reset_index(drop=True))
    tmp["norm_name"] = tmp["ingredient_name"].map(normalize_name)
    tmp["ingredient_id"] = tmp.index + 1
    normalized_df = tmp[["ingredient_id","ingredient_name","norm_name"]]
else:
    normalized_df = recipes_raw[["ingredient_id","ingredient_name","norm_name"]].drop_duplicates()

# --- quantities lookup from recipes ---
if "quantity_text" in recipes_raw.columns:
    qty_df = (recipes_raw[["quantity_text"]]
              .rename(columns={"quantity_text":"amount_text"})
              .dropna().drop_duplicates().reset_index(drop=True))
    qty_df["quantity_id"] = qty_df.index + 1
    qty_df = qty_df[["quantity_id","amount_text"]]
else:
    qty_df = pd.DataFrame({"quantity_id":[1], "amount_text":["1 unit"]})

# --- recipe table (dedupe)
recipe_df = (recipes_raw[["title","url","image_url","serves","time"]]
             .drop_duplicates().reset_index(drop=True))
recipe_df["recipe_id"] = recipe_df.index + 100  # stable example offset
recipe_df = recipe_df[["recipe_id","title","url","image_url","serves","time"]]

# --- build Cookbook link: recipe_id x ingredient_id x quantity_id ---
# Expect recipes_raw to have columns: title, ingredient_name, quantity_text
cookbook_df = (recipes_raw.merge(recipe_df, on="title")
               .merge(normalized_df, on="ingredient_name", how="left")
               )

if "quantity_text" in recipes_raw.columns:
    cookbook_df = (cookbook_df
                   .merge(qty_df, left_on="quantity_text", right_on="amount_text", how="left"))
else:
    cookbook_df["quantity_id"] = 1

cookbook_link = cookbook_df[["recipe_id","ingredient_id","quantity_id"]].dropna().drop_duplicates()

# --- TJ product catalog (combine product CSVs) ---
products["category"] = "center_store"
fruit_veg["category"] = "produce"
meat["category"] = "meat"

prod_all = pd.concat([products, fruit_veg, meat], ignore_index=True).drop_duplicates()
# Expect a column with product name; adapt if yours is different:
name_col = "name" if "name" in prod_all.columns else prod_all.columns[0]
prod_all["standardized_name"] = prod_all[name_col].astype(str).str.strip()
prod_all["norm_name"] = prod_all["standardized_name"].map(normalize_name)

# If you have a size/weight column, map it; else create a free-text package size
pkg_col = "size" if "size" in prod_all.columns else None
prod_all["package_size_text"] = prod_all[pkg_col] if pkg_col else None
prod_all["product_id"] = prod_all.index + 1

tj_product_df = prod_all[["product_id","standardized_name","norm_name","category","package_size_text"]]

# --- sold_as mapping: match products to normalized ingredients by norm_name ---
sold_as_df = (tj_product_df.merge(normalized_df[["ingredient_id","norm_name"]], on="norm_name", how="inner")
              [["product_id","ingredient_id"]].drop_duplicates())

# --- create SQLite DB and schema ---
engine = create_engine("sqlite:///cookbook.db", echo=False)

schema_sql = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS recipe(
  recipe_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT,
  image_url TEXT,
  serves TEXT,
  time TEXT
);

CREATE TABLE IF NOT EXISTS normalized_ingredient(
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
  quantity_id INTEGER,
  PRIMARY KEY (recipe_id, ingredient_id, quantity_id),
  FOREIGN KEY (recipe_id) REFERENCES recipe(recipe_id) ON DELETE CASCADE,
  FOREIGN KEY (ingredient_id) REFERENCES normalized_ingredient(ingredient_id) ON DELETE CASCADE,
  FOREIGN KEY (quantity_id) REFERENCES quantity(quantity_id)
);

CREATE TABLE IF NOT EXISTS pantry(
  pantry_id INTEGER PRIMARY KEY,
  ingredient_id INTEGER NOT NULL,
  amount REAL,
  units TEXT,
  added_date TEXT,
  expiration_date TEXT,
  FOREIGN KEY (ingredient_id) REFERENCES normalized_ingredient(ingredient_id)
);

CREATE TABLE IF NOT EXISTS expiration_dates(
  expiration_id INTEGER PRIMARY KEY,
  ingredient_id INTEGER NOT NULL,
  expiration_days INTEGER,
  FOREIGN KEY (ingredient_id) REFERENCES normalized_ingredient(ingredient_id)
);

CREATE TABLE IF NOT EXISTS tj_product(
  product_id INTEGER PRIMARY KEY,
  standardized_name TEXT NOT NULL,
  norm_name TEXT,
  category TEXT,
  package_size_text TEXT
);

CREATE TABLE IF NOT EXISTS sold_as(
  product_id INTEGER NOT NULL,
  ingredient_id INTEGER NOT NULL,
  PRIMARY KEY (product_id, ingredient_id),
  FOREIGN KEY (product_id) REFERENCES tj_product(product_id),
  FOREIGN KEY (ingredient_id) REFERENCES normalized_ingredient(ingredient_id)
);

-- fast lookups
CREATE INDEX IF NOT EXISTS idx_ckbk_recipe ON cookbook(recipe_id);
CREATE INDEX IF NOT EXISTS idx_ckbk_ing ON cookbook(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_prod_norm ON tj_product(norm_name);
CREATE INDEX IF NOT EXISTS idx_ing_norm ON normalized_ingredient(norm_name);

-- convenience view: ingredient -> recipe
CREATE VIEW IF NOT EXISTS ingredient_recipe_inverted_index AS
SELECT ingredient_id, recipe_id
FROM cookbook
GROUP BY ingredient_id, recipe_id;
"""

with engine.begin() as con:
    con.execute(text(schema_sql))

# --- load data into SQLite ---
recipe_df.rename(columns={"title":"name"}, inplace=True)
recipe_df.to_sql("recipe", engine, if_exists="replace", index=False)
normalized_df.rename(columns={"ingredient_name":"raw_name"}, inplace=True)
normalized_df.to_sql("normalized_ingredient", engine, if_exists="replace", index=False)
qty_df.to_sql("quantity", engine, if_exists="replace", index=False)
cookbook_link.to_sql("cookbook", engine, if_exists="replace", index=False)
tj_product_df.to_sql("tj_product", engine, if_exists="replace", index=False)
sold_as_df.to_sql("sold_as", engine, if_exists="replace", index=False)

print("✅ Database created: cookbook.db")
print(f"recipes: {len(recipe_df)}, ingredients: {len(normalized_df)}, quantities: {len(qty_df)}, cookbook links: {len(cookbook_link)}")
print(f"TJ products: {len(tj_product_df)}, sold_as links: {len(sold_as_df)}")