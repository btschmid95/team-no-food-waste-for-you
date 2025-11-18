from sqlalchemy.orm import Session
from services.pantry_manager import PantryManager
from recommender_system.recipe_recommender_sys import RecipeRecommender
from database.tables import Recipe, PantryItem
from datetime import datetime

class RecipeRecommender:

    def __init__(self, session: Session):
        self.session = session
        self.pm = PantryManager(session)

    # Calculate waste score for all pantry items
    def calculate_item_scores(self, virtual_state=None):
        """
        Returns {product_id: waste_score}
        If virtual_state is provided, compute scores from that.
        """
        if virtual_state is None:
            items = self.pm.get_all_items()
        else:
            items = self.pm.import_state(virtual_state)

        return {
            item["product_id"]: self.pm.compute_waste_score_from_snapshot(item)
            for item in items
        }

    # Score a single recipe
    def score_recipe(self, recipe: Recipe, item_scores: dict, virtual_state=None):
        total_score = 0
        matched = 0
        missing = 0
        external = 0

        for ing in recipe.ingredients:

            if not ing.matched_product:
                external += 1
                continue

            product_id = ing.matched_product_id
            recipe_amt = ing.amount or 0

            # Get pantry amount from virtual state
            if virtual_state is None:
                pantry_item = (
                    self.session.query(PantryItem)
                    .filter_by(product_id=product_id)
                    .first()
                )
                pantry_amt = pantry_item.amount if pantry_item else 0
            else:
                pantry_amt = virtual_state.get(product_id, {}).get("amount", 0)

            if pantry_amt <= 0:
                missing += 1
                continue

            matched += 1

            TWRS = item_scores.get(product_id, 0)

            utilization_ratio = min(recipe_amt / pantry_amt, 1.0) if pantry_amt else 0.0
            item_contribution = TWRS * utilization_ratio
            total_score += item_contribution

            if recipe_amt > pantry_amt:
                missing += 1

        return {
            "recipe_id": recipe.recipe_id,
            "title": recipe.title,
            "score": total_score,
            "matched": matched,
            "missing": missing,
            "external": external,
        }

    # Recommend top recipes
    def recommend_recipes(self, limit=5, max_missing=1, virtual_pantry_state=None):
        item_scores = self.calculate_item_scores(virtual_pantry_state)
        recipes = self.session.query(Recipe).all()

        scored = [
            self.score_recipe(r, item_scores, virtual_pantry_state)
            for r in recipes
        ]

        filtered = [s for s in scored if s["missing"] <= max_missing]
        ranked = sorted(filtered, key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    # Explain rationale
    def get_rationale(self, recipe_id):
        recipe = (
            self.session.query(Recipe)
            .filter_by(recipe_id=recipe_id)
            .first()
        )

        rationale = []
        for ing in recipe.ingredients:
            exp_days = None

            if ing.matched_product:
                pantry_item = (
                    self.session.query(PantryItem)
                    .filter_by(product_id=ing.matched_product_id)
                    .first()
                )
                if pantry_item and pantry_item.expiration_date:
                    exp_days = (pantry_item.expiration_date - datetime.now()).days

            rationale.append({
                "ingredient": ing.name,
                "matched_product": ing.matched_product.name if ing.matched_product else None,
                "expires_in_days": exp_days,
                "is_external": ing.matched_product is None,
            })

        return rationale
