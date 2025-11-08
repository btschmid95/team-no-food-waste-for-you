from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey, Table, DateTime, create_engine
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

sold_as_table = Table(
    "sold_as",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("tj_inventory.product_id"), primary_key=True),
    Column("ingredient_id", Integer, ForeignKey("usable_ingredients.ingredient_id"), primary_key=True)
)

class Recipe(Base):
    __tablename__ = "recipe"
    recipe_id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    url = Column(Text)
    image_url = Column(Text)
    serves = Column(Text)
    time = Column(Text)
    category = Column(Text)

    ingredients = relationship("Cookbook", back_populates="recipe")

class UsableIngredient(Base):
    __tablename__ = "usable_ingredients"
    ingredient_id = Column(Integer, primary_key=True)
    raw_name = Column(Text)
    norm_name = Column(Text, nullable=False)

    recipes = relationship("Cookbook", back_populates="ingredient")
    tj_products = relationship("TJInventory", secondary=sold_as_table, back_populates="ingredients")
    pantry_items = relationship("Pantry", back_populates="ingredient")
    shelf_life = relationship("ShelfLife", back_populates="ingredient", uselist=False)

class Quantity(Base):
    __tablename__ = "quantity"
    quantity_id = Column(Integer, primary_key=True)
    amount_text = Column(Text, nullable=False)

    cookbook_entries = relationship("Cookbook", back_populates="quantity")

class Cookbook(Base):
    __tablename__ = "cookbook"
    recipe_id = Column(Integer, ForeignKey("recipe.recipe_id"), primary_key=True)
    ingredient_id = Column(Integer, ForeignKey("usable_ingredients.ingredient_id"), primary_key=True)
    quantity_id = Column(Integer, ForeignKey("quantity.quantity_id"), primary_key=True)

    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("UsableIngredient", back_populates="recipes")
    quantity = relationship("Quantity", back_populates="cookbook_entries")

# --- Pantry Tables ---
class ShelfLife(Base):
    __tablename__ = "shelf_life"
    ingredient_id = Column(Integer, ForeignKey("usable_ingredients.ingredient_id"), primary_key=True)
    shelf_life_days = Column(Integer, nullable=False)

    ingredient = relationship("UsableIngredient", back_populates="shelf_life")

class Pantry(Base):
    __tablename__ = "pantry"
    pantry_id = Column(Integer, primary_key=True)
    ingredient_id = Column(Integer, ForeignKey("usable_ingredients.ingredient_id"), nullable=False)
    amount = Column(Float)
    unit = Column(Text)
    date_purchased = Column(Text)
    expiration_date = Column(Text)

    ingredient = relationship("UsableIngredient", back_populates="pantry_items")

# --- TJ Inventory Tables ---
class TJInventory(Base):
    __tablename__ = "tj_inventory"

    product_id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    norm_name = Column(Text)
    unit = Column(Text)
    price = Column(Float)
    url = Column(Text)
    category = Column(Text)
    sub_category = Column(Text)

    ingredients = relationship("UsableIngredient", secondary=sold_as_table, back_populates="tj_products")


class RecipeRecommended(Base):
    __tablename__ = "recipe_recommended"
    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("recipe.recipe_id"))
    date = Column(Text)
    recipe = Column(Text)

class RecipeSelected(Base):
    __tablename__ = "recipe_selected"
    sel_id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("recipe.recipe_id"))
    sel_ts = Column(Text, default=lambda: datetime.now().isoformat())

class RawIngredient(Base):
    __tablename__ = "raw_ingredients"
    raw_ing_id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipe.recipe_id"))
    raw_text = Column(Text)

# --- Utility function ---
def create_all_tables(engine):
    Base.metadata.create_all(engine)
