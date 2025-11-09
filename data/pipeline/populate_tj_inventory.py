from pathlib import Path
import sys
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# --- Project setup ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from setup.tables import Base, TJInventory
from data.ingredient_normalization import normalize

# --- Helpers ---
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


def populate_tj_inventory_v3(csv_path: Path, db_path: Path):
    """
    Populate TJ Inventory (v3) into SQLite database.
    """
    # --- Resolve paths ---
    csv_path = csv_path.resolve()
    db_path = db_path.resolve()

    if not csv_path.exists():
        raise FileNotFoundError(f"TJ inventory CSV not found at {csv_path}")

    # --- Load CSV ---
    tj_inventory = pd.read_csv(csv_path)

    # --- Create or connect to database ---
    engine_url = f"sqlite:///{db_path}"
    engine = create_engine(engine_url, echo=False)
    Base.metadata.create_all(engine)

    # --- Normalize + prepare data ---
    tj = pd.DataFrame({
        "name": tj_inventory["product_name"],
        "norm_name": tj_inventory["product_name"].apply(lambda x: normalize(x) if isinstance(x, str) else x),
        "unit": tj_inventory.get("unit"),
        "price": tj_inventory.get("price").map(parse_price_to_float) if "price" in tj_inventory.columns else None,
        "url": tj_inventory.get("url"),
        "category": tj_inventory.get("category"),
        "sub_category": tj_inventory.get("sub_category"),
    })

    # --- Drop duplicates and add product_id ---
    tj = tj.drop_duplicates(subset=["name", "unit", "price", "sub_category"]).reset_index(drop=True)
    tj["product_id"] = tj.index + 1
    tj = tj[["product_id", "name", "norm_name", "unit", "price", "url", "category", "sub_category"]]

    # --- Insert into database ---
    with Session(engine) as session:
        for _, row in tj.iterrows():
            product = TJInventory(
                product_id=row["product_id"],
                name=row["name"],
                norm_name=row["norm_name"],
                unit=row["unit"],
                price=row["price"],
                url=row["url"],
                category=row["category"],
                sub_category=row["sub_category"],
            )
            session.merge(product)
        session.commit()

    print(f"✅ Populated TJ Inventory v3 into {db_path.name}: {len(tj)} products inserted/updated.")


# --- Run standalone ---
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    csv_path = project_root / "data" / "trader_joes_products_v3.csv"
    db_path = project_root / "team-no-food-waste-for-you.sqlite"

    populate_tj_inventory_v3(csv_path, db_path)
