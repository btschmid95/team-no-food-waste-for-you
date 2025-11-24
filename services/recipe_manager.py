# services/recipe_manager.py
import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from recommender_system.recipe_recommender_sys import RecipeRecommender
from services.pantry_manager import PantryManager
from database.tables import (
    Recipe,
    Ingredient,
    TJInventory,
    PantryItem,
    PantryEvent,
    RecipeSelected,
)

class RecipeManager:

    def __init__(self, session: Session):
        self.session = session

    def get_all_recipes(self):
        return self.session.query(Recipe).all()

    def get_recipe_by_id(self, recipe_id: int):
        return self.session.query(Recipe).filter_by(recipe_id=recipe_id).first()

    def get_ingredients_for_recipe(self, recipe_id: int):
        return (
            self.session.query(Ingredient)
            .filter_by(recipe_id=recipe_id)
            .all()
        )

    def get_recommendations(self, max_missing=1, limit=5, virtual_state=None):
        rr = RecipeRecommender(self.session)
        return rr.recommend_recipes(
            limit=limit,
            max_missing=max_missing,
            virtual_pantry_state=virtual_state
        )

    def add_recipe_to_planning_queue(self, recipe_id: int, planned_for=None):
        planned = RecipeSelected(
            recipe_id=recipe_id,
            planned_for=planned_for,
            selected_at=datetime.now()
        )
        self.session.add(planned)
        self.session.commit()
        return planned

    def get_planning_queue(self):
        return (
            self.session.query(RecipeSelected)
            .order_by(RecipeSelected.planned_for.asc())
            .all()
        )

    def update_planned_date(self, sel_id: int, planned_str):
        """planned_str may be a string ('2025-11-22') or a datetime/date object."""
        planned = self.session.query(RecipeSelected).filter_by(sel_id=sel_id).first()
        if not planned:
            return None

        if isinstance(planned_str, str):
            try:
                planned_date = datetime.fromisoformat(planned_str)
            except ValueError:
                planned_date = None
        elif isinstance(planned_str, datetime):
            planned_date = planned_str
        elif hasattr(planned_str, "isoformat"):
            planned_date = datetime.combine(planned_str, datetime.min.time())
        else:
            planned_date = None

        planned.planned_for = planned_date
        self.session.commit()
        return planned

    def confirm_recipe(self, sel_id: int):

        planned = (
            self.session.query(RecipeSelected)
            .filter_by(sel_id=sel_id)
            .first()
        )
        if not planned:
            return None

        recipe_id = planned.recipe_id
        planned_date = planned.planned_for.date() if planned.planned_for else datetime.now().date()

        pm = PantryManager(self.session)
        grocery_list = pm.get_grocery_list([recipe_id])

        if grocery_list:
            pm.add_grocery_list(grocery_list, planned_date)

        pm.consume_recipe(recipe_id, sel_id)

        planned.cooked_at = datetime.now()
        self.session.commit()

        return planned

    
    def get_planned_consumption_by_date(self):
        """
        Returns a DataFrame:
        date | planned_consumption
        """
        selections = (
            self.session.query(RecipeSelected)
            .filter(RecipeSelected.planned_for.isnot(None))
            .all()
        )

        if not selections:
            return pd.DataFrame(columns=["date", "planned_consumption"])

        rows = []

        for sel in selections:
            recipe_id = sel.recipe_id
            date = sel.planned_for.date()
            ingredients = self.get_ingredients_for_recipe(recipe_id)

            for ing in ingredients:
                if ing.amount is None:
                    continue

                rows.append({
                    "date": date,
                    "amount": ing.amount
                })

        df = pd.DataFrame(rows)

        if df.empty:
            return pd.DataFrame(columns=["date", "planned_consumption"])

        daily = (
            df.groupby("date", as_index=False)["amount"]
              .sum()
              .rename(columns={"amount": "planned_consumption"})
        )

        return daily

    def update_meal_slot(self, sel_id: int, slot: str):
        """Update meal slot for a planned recipe."""
        planned = self.session.query(RecipeSelected).filter_by(sel_id=sel_id).first()
        if not planned:
            return None

        planned.meal_slot = slot
        self.session.commit()
        return planned
    
    def delete_planned_recipe(self, sel_id: int):
        planned = (
            self.session.query(RecipeSelected)
            .filter_by(sel_id=sel_id)
            .first()
        )
        if planned:
            self.session.delete(planned)
            self.session.commit()
            return True
        return False

