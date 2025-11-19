# services/recipe_manager.py
import pandas as pd
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

    # 💡 1. Fetching Recipes & Ingredients
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

    # ⭐ 2. Recommendation API Hook (stub)
    def get_recommendations(self, max_missing=1, limit=5, virtual_state=None):
        rr = RecipeRecommender(self.session)
        return rr.recommend_recipes(
            limit=limit,
            max_missing=max_missing,
            virtual_pantry_state=virtual_state
        )

    # 📌 3. Planning Queue Management
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

    def update_planned_date(self, sel_id: int, date):
        planned = self.session.query(RecipeSelected).filter_by(sel_id=sel_id).first()
        if planned:
            planned.planned_for = date
            self.session.commit()
        return planned
    
    # ✔️ 4. Confirm Recipe (Core Logic)
    def confirm_recipe(self, sel_id: int):
        planned = self.session.query(RecipeSelected).filter_by(sel_id=sel_id).first()
        if not planned:
            return None

        recipe_id = planned.recipe_id

        # Full FEFO-based consumption handled by PantryManager
        pm = PantryManager(self.session)
        pm.apply_recipe(recipe_id)

        planned.cooked_at = datetime.now()
        self.session.commit()

        return planned
    
    def get_planned_consumption_by_date(self):
        """
        Returns a DataFrame:
        date | planned_consumption
        """

        # 1. Load all planned recipes
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

            # 2. Ingredients for this recipe
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

        # 3. Aggregate by date
        daily = (
            df.groupby("date", as_index=False)["amount"]
              .sum()
              .rename(columns={"amount": "planned_consumption"})
        )

        return daily
