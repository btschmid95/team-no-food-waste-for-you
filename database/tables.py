from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey, Table, DateTime, create_engine
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Recipe(Base):
    __tablename__ = "recipe"

    recipe_id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    url = Column(Text)
    image_url = Column(Text)
    serves = Column(Text)
    time = Column(Text)
    category = Column(Text)

    # One-to-many → Ingredient
    ingredients = relationship("Ingredient", back_populates="recipe")

class Ingredient(Base):
    __tablename__ = "ingredient"

    ingredient_id = Column(Integer, primary_key=True, autoincrement=True)

    recipe_id = Column(Integer, ForeignKey("recipe.recipe_id"), nullable=False)
    raw_text = Column(Text, nullable=False)

    # Parsed info
    name = Column(Text, nullable=True)
    norm_name = Column(Text, nullable=True)
    amount = Column(Float, nullable=True)
    unit = Column(Text, nullable=True)

    # Product assignment
    matched_product_id = Column(Integer, ForeignKey("tj_inventory.product_id"), nullable=True)

    pantry_amount = Column(Float, nullable=True)
    pantry_unit = Column(Text, nullable=True)

    recipe = relationship("Recipe", back_populates="ingredients")
    matched_product = relationship(
        "TJInventory",
        back_populates="ingredients",
        foreign_keys=[matched_product_id]
    )

class TJInventory(Base):
    __tablename__ = "tj_inventory"

    product_id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    norm_name = Column(Text)
    unit = Column(Text)
    quantity = Column(Float)
    price = Column(Float)
    url = Column(Text)
    category = Column(Text)
    sub_category = Column(Text)
    shelf_life_days = Column(Integer, nullable=True)

    # Reverse relation: ingredients mapped to this product
    ingredients = relationship(
        "Ingredient",
        back_populates="matched_product",
        foreign_keys="Ingredient.matched_product_id",
        primaryjoin="TJInventory.product_id == Ingredient.matched_product_id"
    )
class PantryItem(Base):
    __tablename__ = "pantry"

    pantry_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("tj_inventory.product_id"), nullable=False)

    amount = Column(Float, nullable=True)
    unit = Column(Text, nullable=True)

    date_added = Column(DateTime, default=datetime.now)
    expiration_date = Column(DateTime, nullable=True)
    # expiration_date = date_added + timedelta(days=product.shelf_life_days)

    product = relationship("TJInventory")

class PantryEvent(Base):
    __tablename__ = "pantry_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pantry_id = Column(Integer, ForeignKey("pantry.pantry_id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now)

    # "consume", "trash", "adjust", etc.
    event_type = Column(Text, nullable=False)

    amount = Column(Float, nullable=True)
    unit = Column(Text, nullable=True)

    # Optional link to recipe usage:
    recipe_selection_id = Column(Integer, ForeignKey("recipe_selected.sel_id"),
                                 nullable=True)

    pantry_item = relationship("PantryItem")
    recipe_selection = relationship("RecipeSelected", back_populates="pantry_events")

class RecipeRecommended(Base):
    __tablename__ = "recipe_recommended"
    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("recipe.recipe_id"))
    recommended_at = Column(DateTime, default=datetime.now)
    score = Column(Float, nullable=True)  #### waste reduction score, model score, etc.

    recipe = relationship("Recipe")

class RecipeSelected(Base):
    __tablename__ = "recipe_selected"
    sel_id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("recipe.recipe_id"))
    selected_at = Column(DateTime, default=datetime.now)

    # When user plans to cook it (optional)
    planned_for = Column(DateTime, nullable=True)
    # When they actually cooked it (optional)
    cooked_at = Column(DateTime, nullable=True)

    recipe = relationship("Recipe")
    pantry_events = relationship("PantryEvent", back_populates="recipe_selection")


class IngredientParseMeta(Base):
    __tablename__ = "ingredient_parse_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Link to Ingredient (correct table!)
    ingredient_id = Column(Integer,
                           ForeignKey("ingredient.ingredient_id"),
                           nullable=False)

    # Original raw text
    raw_text = Column(Text, nullable=True)

    # Parsed name
    parsed_name = Column(Text, nullable=True)

    # Parsed quantities
    amount = Column(Float, nullable=True)
    amount_unit = Column(Text, nullable=True)

    # ML category predictions (top 3)
    subcat_1 = Column(Text)
    subcat_1_score = Column(Float)
    maincat_1 = Column(Text)

    subcat_2 = Column(Text)
    subcat_2_score = Column(Float)
    maincat_2 = Column(Text)

    subcat_3 = Column(Text)
    subcat_3_score = Column(Float)
    maincat_3 = Column(Text)

    # Optional: preparation text
    preparation = Column(Text)
    preparation_confidence = Column(Float)

    # Recipe context (useful debugging fields)
    recipe_title = Column(Text)
    recipe_category = Column(Text)

    created_at = Column(DateTime, default=datetime.now)

    # Relationship (optional, but recommended)
    ingredient = relationship("Ingredient", backref="parse_meta")

# --- Utility function ---
def create_all_tables(engine):
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    from sqlalchemy.orm import sessionmaker
    from config import DATABASE_URL
    from sqlalchemy import text
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]  # the repo's root directory
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    from services.pantry_manager import PantryManager

    print("Connecting to DB:", DATABASE_URL)

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    def print_header(title):
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)

    # --------------------------------------------------
    # 0. Print row counts for all tables
    # --------------------------------------------------
    tables = [
        "recipe",
        "ingredient",
        "tj_inventory",
        "pantry",
        "pantry_event",
        "recipe_selected",
        "recipe_recommended",
        "ingredient_parse_meta",
    ]

    print_header("ROW COUNTS")
    for t in tables:
        try:
            count = session.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"{t}: {count}")
        except Exception as e:
            print(f"{t}: ERROR: {e}")

    # --------------------------------------------------
    # 1. Ingredient sample
    # --------------------------------------------------
    print_header("INGREDIENT SAMPLE (20 rows)")
    sample = (
        session.query(
            Ingredient.ingredient_id,
            Ingredient.recipe_id,
            Ingredient.raw_text,
            Ingredient.amount,
            Ingredient.unit,
            Ingredient.pantry_amount,
            Ingredient.pantry_unit,
            Ingredient.matched_product_id,
        )
        .limit(20)
        .all()
    )
    for row in sample:
        print(row)

    # --------------------------------------------------
    # 2. Pantry sample
    # --------------------------------------------------
    print_header("PANTRY SAMPLE (20 rows)")
    sample = (
        session.query(
            PantryItem.pantry_id,
            PantryItem.product_id,
            PantryItem.amount,
            PantryItem.unit,
            PantryItem.date_added,
            PantryItem.expiration_date,
        )
        .limit(20)
        .all()
    )
    for row in sample:
        print(row)

    # --------------------------------------------------
    # 3. TJ Inventory sample
    # --------------------------------------------------
    print_header("TJ INVENTORY SAMPLE (20 rows)")
    sample = (
        session.query(
            TJInventory.product_id,
            TJInventory.name,
            TJInventory.norm_name,
            TJInventory.quantity,
            TJInventory.unit,
            TJInventory.category,
            TJInventory.sub_category,
            TJInventory.shelf_life_days,
        )
        .limit(20)
        .all()
    )
    for row in sample:
        print(row)

    # --------------------------------------------------
    # 4. Orphan Pantry rows (invalid product_id)
    # --------------------------------------------------
    print_header("ORPHAN PANTRY ITEMS (Pantry rows referencing missing TJ products)")
    orphans = (
        session.query(
            PantryItem.pantry_id,
            PantryItem.product_id,
            PantryItem.amount,
        )
        .outerjoin(TJInventory, PantryItem.product_id == TJInventory.product_id)
        .filter(TJInventory.product_id == None)
        .all()
    )
    print(f"Total orphaned pantry items: {len(orphans)}")
    for row in orphans[:20]:
        print(row)

    # --------------------------------------------------
    # 5. Ingredients referencing missing TJInventory entries
    # --------------------------------------------------
    print_header("ORPHAN INGREDIENTS (Ingredients with invalid matched_product_id)")
    bad_ing = (
        session.query(
            Ingredient.ingredient_id,
            Ingredient.raw_text,
            Ingredient.matched_product_id,
        )
        .outerjoin(TJInventory, Ingredient.matched_product_id == TJInventory.product_id)
        .filter(
            Ingredient.matched_product_id.isnot(None),
            TJInventory.product_id == None,
        )
        .all()
    )
    print(f"Total orphaned ingredients: {len(bad_ing)}")
    for row in bad_ing[:20]:
        print(row)

    # --------------------------------------------------
    # 6. Recipe sample
    # --------------------------------------------------
    print_header("RECIPE SAMPLE (20 rows)")
    sample = session.query(Recipe).limit(20).all()
    for r in sample:
        print(r.recipe_id, r.title, r.url)
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import create_engine
    from database.config import DATABASE_URL
    from database.tables import PantryItem, TJInventory, Ingredient, Recipe
    from services.pantry_manager import PantryManager
    from recommender_system.recipe_recommender_sys import RecipeRecommender

    # --- DB Setup ---
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # --- Instantiate pantry + recommender ---
    pm = PantryManager(session)
    rec = RecipeRecommender(session)

    # --- 1. Print raw pantry rows directly from DB ---
    print("=== RAW PANTRY ROWS FROM DB ===")
    raw = session.query(PantryItem).all()
    print("Count in DB:", len(raw))
    for p in raw:
        print(p.pantry_id, p.product_id, p.amount, p.unit, p.expiration_date)
    print()

    # --- 2. Print get_all_items() output ---
    print("=== get_all_items() OUTPUT ===")
    items = pm.get_all_items()
    print("Count returned by get_all_items():", len(items))
    for item in items:
        print(item)
    print()

    # # --- 3. Print waste scores for each returned item ---
    # print("=== WASTE SCORES ===")
    # scores = rec.calculate_item_scores()
    # print("Count returned by calculate_item_scores:", len(scores))

    # for pid, score in scores.items():
    #     print(f"product_id={pid:4} | waste_score={score:.4f}")
    from database.tables import Ingredient, TJInventory
    from sqlalchemy import or_

    results = (
        session.query(
            Ingredient.ingredient_id,
            Ingredient.raw_text,
            Ingredient.name,
            Ingredient.matched_product_id,
            TJInventory.name.label("product_name")
        )
        .outerjoin(TJInventory, Ingredient.matched_product_id == TJInventory.product_id)
        .filter(
            or_(
                Ingredient.raw_text.ilike("%parsley%"),
                Ingredient.name.ilike("%parsley%")
            )
        )
        .order_by(Ingredient.ingredient_id)
        .all()
    )

    for row in results:
        print("Ingredient ID:", row.ingredient_id)
        print("Raw Text:", row.raw_text)
        print("Parsed Name:", row.name)
        print("Matched Product ID:", row.matched_product_id)
        print("Matched Product Name:", row.product_name)
        print("-" * 60)
    print("\n=== DEBUG COMPLETE ===")