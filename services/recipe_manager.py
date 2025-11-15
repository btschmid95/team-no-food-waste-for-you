# services/recipe_manager.py

from sqlalchemy.orm import Session
from datetime import datetime, timedelta

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

    # ---------------------------------------------------------
    # 💡 1. Fetching Recipes & Ingredients
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # ⭐ 2. Recommendation API Hook (stub)
    # ---------------------------------------------------------
    def get_recommended_recipes(self, max_missing=1, limit=5):
        """
        This will later call recommender_system.recipe_recommender.
        For now: placeholder.
        """
        return (
            self.session.query(Recipe)
            .limit(limit)
            .all()
        )

    # ---------------------------------------------------------
    # 📌 3. Planning Queue Management
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # ✔️ 4. Confirm Recipe (Core Logic)
    # ---------------------------------------------------------
    def confirm_recipe(self, sel_id: int):
        """
        Once a recipe is confirmed:
        - Missing items are added to pantry as new purchases
        - Existing pantry stock is consumed
        - PantryEvents are created
        """

        planned = self.session.query(RecipeSelected).filter_by(sel_id=sel_id).first()
        if not planned:
            return None

        recipe_id = planned.recipe_id
        ingredients = self.get_ingredients_for_recipe(recipe_id)

        # Loop through recipe ingredients and apply logic
        for ing in ingredients:
            product = ing.matched_product

            if not product:
                continue  # No mapping → skip for now

            # TODO: Compare ingredient amount needed vs pantry stock

            # Example placeholder logic:
            event = PantryEvent(
                pantry_id=None,           # will fill in later
                event_type="consume",
                amount=ing.amount,
                unit=ing.unit,
                timestamp=datetime.now(),
                recipe_selection_id=sel_id
            )
            self.session.add(event)

        planned.cooked_at = datetime.now()
        self.session.commit()

        return planned
