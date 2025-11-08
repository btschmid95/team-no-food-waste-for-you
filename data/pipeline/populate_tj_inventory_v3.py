# data/pipeline/populate_tj_inventory.py

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from data.models import TJInventory, Base
from data.ingredient_normalization import normalize


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


def populate_tj_inventory_v3(csv_path: str, engine_url: str):
    """
    Reads TJ inventory v3 CSV, normalizes product names, and populates the tj_inventory table.
    
    Args:
        csv_path (str): Path to TJ inventory v3 CSV.
        engine_url (str): SQLAlchemy engine URL.
    """
    # Load CSV
    tj_inventory = pd.read_csv(csv_path)

    # Create engine and tables if not exist
    engine = create_engine(engine_url, echo=False)
    Base.metadata.create_all(engine)

    # Prepare DataFrame
    tj = pd.DataFrame({
        "name": tj_inventory["product_name"],
        "norm_name": tj_inventory["product_name"].apply(lambda x: normalize(x) if isinstance(x, str) else x),
        "unit": tj_inventory.get("unit"),
        "price": tj_inventory.get("price").map(parse_price_to_float) if "price" in tj_inventory.columns else None,
        "url": tj_inventory.get("url"),
        "category": tj_inventory.get("category"),
        "sub_category": tj_inventory.get("sub_category")
    })

    # Drop exact duplicates
    tj = tj.drop_duplicates(subset=["name", "unit", "price", "sub_category"]).reset_index(drop=True)

    # Assign product_id
    tj["product_id"] = tj.index + 1

    # Reorder columns
    tj = tj[["product_id", "name", "norm_name", "unit", "price", "url", "category", "sub_category"]]

    # Insert into database
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
                sub_category=row["sub_category"],  # make sure this exists in the model
            )
            session.merge(product)
        session.commit()
    
    print(f"✅ TJ inventory v3 populated: {len(tj)} products.")


# Example usage
if __name__ == "__main__":
    populate_tj_inventory_v3(
        csv_path="../data/trader_joes_products_v3.csv",
        engine_url="sqlite:///cookbook.db"
    )
