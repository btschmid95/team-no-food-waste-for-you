from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.tables import TJInventory, Ingredient
from database.config import DATABASE_URL
from database.normalization import normalize

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class ProductManager:
    def __init__(self, session: Session = None):
        self.session = session or SessionLocal()

    def add_new_product(self, name, unit=None, price=None,
                        url=None, category=None, sub_category=None,
                        shelf_life_days=None):
        """
        Add a new product to the TJInventory table.
        Applies canonical normalization via normalization.py
        """
        normalized_name = normalize(name)

        new_product = TJInventory(
            name=name,
            norm_name=normalized_name,
            unit=unit,
            price=price,
            url=url,
            category=category,
            sub_category=sub_category,
            shelf_life_days=shelf_life_days
        )

        self.session.add(new_product)
        self.session.commit()

        return f"Added product '{name}' (ID: {new_product.product_id})"

    def remove_existing_product(self, product_id):
        product = self.get_product(product_id)
        if not product:
            return f"Product {product_id} not found."

        self.session.delete(product)
        self.session.commit()

        return f"Removed product '{product.name}' (ID: {product_id})"

    def get_product(self, product_id):
        return (
            self.session.query(TJInventory)
            .filter(TJInventory.product_id == product_id)
            .first()
        )

    def get_product_price(self, product_id):
        product = self.get_product(product_id)
        return product.price if product else None

    def get_product_unit(self, product_id):
        product = self.get_product(product_id)
        return product.unit if product else None

    def get_product_category(self, product_id):
        product = self.get_product(product_id)
        return product.category if product else None

    def get_product_sub_category(self, product_id):
        product = self.get_product(product_id)
        return product.sub_category if product else None

    def get_product_shelf_life(self, product_id):
        product = self.get_product(product_id)
        return product.shelf_life_days if product else None

    def get_all_by_category(self, category):
        """
        Return all products whose category contains the given text.
        """
        return (
            self.session.query(TJInventory)
            .filter(TJInventory.category.ilike(f"%{category}%"))
            .all()
        )

    def list_all_products(self):
        return (
            self.session.query(TJInventory)
            .order_by(TJInventory.name)
            .all()
        )

    def find_by_name(self, name):
        """
        Flexible name search using normalized (canonical) name.
        """
        normalized_query = normalize(name)
        return (
            self.session.query(TJInventory)
            .filter(TJInventory.norm_name.ilike(f"%{normalized_query}%"))
            .all()
        )

    def update_product(self, product_id, **updates):
        """
        Update any subset of product fields.
        Automatically normalizes name if 'name' is changed.
        """
        product = self.get_product(product_id)
        if not product:
            return f"Product {product_id} not found."

        for key, value in updates.items():
            if hasattr(product, key):
                setattr(product, key, value)

        if "name" in updates:
            product.norm_name = normalize(updates["name"])

        self.session.commit()
        return f"Updated product {product_id}"

    def get_product_information(self, product_id):
        """
        Returns all fields as a dictionary.
        """
        product = self.get_product(product_id)
        if not product:
            return None

        return {
            "product_id": product.product_id,
            "name": product.name,
            "norm_name": product.norm_name,
            "unit": product.unit,
            "price": product.price,
            "url": product.url,
            "category": product.category,
            "sub_category": product.sub_category,
            "shelf_life_days": product.shelf_life_days,
        }
    def get_valid_products_for_pantry(self):
        return (
            self.session.query(TJInventory)
            .join(Ingredient, Ingredient.matched_product_id == TJInventory.product_id)
            .filter(Ingredient.pantry_amount.isnot(None))
            .filter(Ingredient.pantry_unit.isnot(None))
            .order_by(TJInventory.name)
            .distinct()
            .all()
        )
        
    def get_valid_products_dict(self):
        products = self.get_valid_products_for_pantry()
        out = []

        for p in products:
            ing = next((i for i in p.ingredients if i.pantry_amount is not None), None)

            if ing is None:
                continue

            out.append({
                "product_id": p.product_id,
                "name": p.name,
                "unit": p.unit,
                "pantry_unit": ing.pantry_unit,
                "pantry_amount": ing.pantry_amount,
                "category": p.category,
                "shelf_life_days": p.shelf_life_days,
            })

        return out
    
if __name__ == "__main__":
    pm = ProductManager()

    print("\n--- First 20 Products ---")
    products = pm.list_all_products()[:20]

    for p in products:
        print(f"{p.product_id}: {p.name}  ({p.category} / {p.sub_category})")

    query = "olive oil"
    print(f"\n--- Searching for: {query} ---")
    results = pm.find_by_name(query)

    for p in results:
        print(f"{p.product_id}: {p.name} → norm({p.norm_name})")

    print("\n--- Product Counts by Category ---")
    from collections import Counter

    all_products = pm.list_all_products()
    counts = Counter(p.category for p in all_products)

    for cat, count in counts.items():
        print(f"{cat}: {count}")

    product_id = 10
    info = pm.get_product_information(product_id)

    print("\n--- Product Info ---")
    print(info)

    category = "Frozen"
    print(f"\n--- Products in '{category}' ---")
    
    results = pm.get_all_by_category(category)

    for p in results:
        print(f"{p.product_id}: {p.name}")