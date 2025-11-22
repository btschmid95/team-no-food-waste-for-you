from sqlalchemy.orm import Session
from services.pantry_manager import PantryManager
from database.tables import Recipe, PantryItem, TJInventory
from datetime import datetime
import streamlit as st

CATEGORY_MULTIPLIERS = {
    "fresh fruits & veggies": 3.0,
    "fresh prepared foods": 3.0,
    "meat, seafood & plant-based": 3.0,

    "cheese": 2.2,
    "dairy & eggs": 2.0,
    "bakery": 1.8,

    "dips, sauces & dressings": 1.0,

    "from the freezer": 1.0,
    "snacks & sweets": 1.0,
    "for the pantry": 1.0,

    "other": 1.0
}

class RecipeRecommender:

    def __init__(self, session: Session):
        self.session = session
        self.pm = PantryManager(session)

        

    # Calculate waste score for all pantry items
    def calculate_item_scores(self, virtual_state=None):
        """
        Returns a list of {product_id, pantry_id, score} for EACH pantry entry.
        No aggregation, no deduplication.
        """

        if virtual_state is None:
            items = self.pm.get_all_items()
        else:
            items = self.pm.import_state(virtual_state) 

        scored = []
        for item in items:
            scored.append({
                "product_id": item["product_id"],
                "expiration_date": item["expiration_date"],
                "amount": item["amount"],
                "waste_score": self._compute_waste_score(item)
            })

        return scored


    def score_recipe(self, recipe: Recipe, item_scores, virtual_state=None):
        """
        Score a recipe based on:
        - waste urgency of each pantry entry (entry-by-entry)
        - FIFO consumption (oldest expiring items used first)
        - utilization ratio per entry
        """

        total_score = 0
        matched = 0
        missing = 0
        external = 0

        # item_scores is now a list, not a dict
        # Convert it to a list of entries per product_id
        score_map = {}
        for entry in item_scores:
            pid = entry["product_id"]
            score_map.setdefault(pid, []).append(entry)

        for ing in recipe.ingredients:

            pid = ing.matched_product_id

            # Ingredient not linked to TJ product
            if not pid:
                external += 1
                continue

            recipe_amt = ing.pantry_amount or 0

            # Collect all pantry entries for this product
            entries = score_map.get(pid, [])

            if not entries:
                missing += 1
                continue

            # We DO have entries, so this ingredient is matched
            matched += 1

            # Sort entries FIFO by expiration date
            entries = sorted(entries, key=lambda e: e["expiration_date"])

            required = recipe_amt
            local_score = 0
            local_missing = False

            for entry in entries:
                if required <= 0:
                    break

                available = entry["amount"]

                if available <= 0:
                    continue

                # How much we use from this entry
                used = min(required, available)

                # Utilization of THIS pantry entry
                utilization = used / available

                # Waste score contribution from THIS entry
                contrib = entry["waste_score"] * utilization
                local_score += contrib

                # Reduce remaining required amount
                required -= used

            # After consuming all entries:
            if required > 0:
                # We didn't have enough stock
                missing += 1

            total_score += local_score

        return {
            "recipe_id": recipe.recipe_id,
            "title": recipe.title,
            "score": round(total_score, 3),
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

        scored = [s for s in scored if s["matched"] > 0]

        scored = [s for s in scored if s["missing"] <= max_missing]
        scored = [s for s in scored if s["score"] > 0]
        ranked = sorted(scored, key=lambda x: x["score"], reverse=True)

        return ranked[:limit]
    def recommend_by_category(self, category, limit=5, max_missing=1, virtual_pantry_state=None):

        item_scores = self.calculate_item_scores(virtual_pantry_state)
        category = category.lower()

        # Select only recipes that match the category
        recipes = [
            r for r in self.session.query(Recipe).all()
            if self.recipe_matches_category(r, category)
        ]

        scored = [
            self.score_recipe(r, item_scores, virtual_pantry_state)
            for r in recipes
        ]

        # Apply your existing filters
        scored = [s for s in scored if s["matched"] > 0]
        scored = [s for s in scored if s["missing"] <= max_missing]
        scored = [s for s in scored if s["score"] > 0]

        ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
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
    def recipe_matches_category(self, recipe, category):
        """Return True if a recipe belongs to the given category keyword."""
        if not recipe.category:
            return False

        raw = recipe.category.lower()
        category = category.lower()
        return category in raw
    
    def _load_real_pantry(self):
        items = (
            self.session.query(PantryItem)
            .all()
        )
        out = []
        for p in items:
            out.append({
                "product_id": p.product_id,
                "amount": p.amount,
                "expiration_date": p.expiration_date,
            })
        return out
    
    def _apply_recipe_to_virtual_state(self, recipe: Recipe, state: dict):
        state = state.copy()

        for ing in recipe.ingredients:
            pid = ing.matched_product_id
            if not pid or pid not in state:
                continue

            required = ing.pantry_amount or 0
            available = state[pid]["amount"]

            new_amount = max(0, available - required)
            state[pid]["amount"] = new_amount

        return state

    def _compute_waste_score(self, item):
        """
        Compute waste score incorporating:
        - shelf-life urgency
        - quantity
        - perishability multiplier based on category
        """

        exp = item.get("expiration_date")
        amt = item.get("amount", 0)

        if not exp or amt <= 0:
            return 0

        # Days until expiration
        days_remaining = (exp - datetime.now()).days

        # Get product category
        product = (
            self.session.query(TJInventory)
            .filter_by(product_id=item["product_id"])
            .first()
        )
        category = (product.sub_category or product.category or "").lower()
        
        # Default multiplier
        mult = CATEGORY_MULTIPLIERS.get(category, CATEGORY_MULTIPLIERS["other"])

        # Expired → highest urgency
        if days_remaining < 0:
            return amt * mult * 5.0

        # Typical curve:
        #   0–3 days → very high urgency
        #   4–10 days → medium
        #   >10 days → low
        urgency = 1 / max(days_remaining, 1)

        score = amt * urgency * mult
        return max(score, 0)
    
    def normalize_category_label(self, recipe: Recipe):
        """Return a clean category label to display on tiles."""
        if not recipe.category:
            return "Uncategorized"
        return recipe.category