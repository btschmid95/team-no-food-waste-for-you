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
    matched_product = relationship("TJInventory", back_populates="ingredients")

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
    ingredients = relationship("Ingredient", back_populates="matched_product")

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
