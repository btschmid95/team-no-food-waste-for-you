from sqlalchemy.orm import Session
from services.pantry_manager import PantryManager
from database.tables import Recipe, PantryItem, TJInventory
from datetime import datetime
import streamlit as st

CATEGORY_MULTIPLIERS = {
    "meat, seafood & plant-based": 8,
    "fresh fruits & veggies": 5,
    "fresh prepared foods": 5,
    "cheese": 2.5,
    "dairy & eggs": 2.5,
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

    def calculate_item_scores(self, virtual_state=None):
        """
        Returns list of:
            { product_id, amount, expiration_date, per_unit_score }
        """

        now = datetime.now()

        # Load either the real pantry or the virtual pantry (FEFO list)
        if virtual_state is None:
            items = self.pm.get_all_items()
        else:
            items = self.pm.import_state(virtual_state)

        scored = []
        for item in items:

            exp = item.get("expiration_date")
            if exp is None:
                continue

            # Ensure expiration is datetime
            if isinstance(exp, datetime):
                exp_dt = exp
            else:
                # If it's a date, convert to datetime at midnight
                exp_dt = datetime.combine(exp, datetime.min.time())

            # Skip expired
            if exp_dt < now:
                continue

            per_unit = self._compute_waste_score(item)

            scored.append({
                "product_id": item["product_id"],
                "expiration_date": exp_dt,
                "amount": item["amount"],
                "per_unit_score": per_unit,
            })

        return scored



    def score_recipe(self, recipe: Recipe, item_scores, virtual_state=None):
        total_score = 0
        matched = 0
        missing = 0
        external = 0

        score_map = {}
        for entry in item_scores:
            pid = entry["product_id"]
            score_map.setdefault(pid, []).append(entry)

        for ing in recipe.ingredients:

            pid = ing.matched_product_id
            if not pid:
                external += 1
                continue

            needed = ing.pantry_amount or 0

            entries = score_map.get(pid, [])
            if not entries:
                missing += 1
                continue
            
            matched += 1

            entries = sorted(entries, key=lambda e: e["expiration_date"])

            required = needed
            local_score = 0

            for entry in entries:
                if required <= 0:
                    break

                avail = entry["amount"]
                if avail <= 0:
                    continue

                used = min(required, avail)
                per_unit = entry["per_unit_score"]
                contrib = per_unit * used
                local_score += contrib
                required -= used

            if required > 0:
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

        recipes = [
            r for r in self.session.query(Recipe).all()
            if self.recipe_matches_category(r, category)
        ]

        scored = [
            self.score_recipe(r, item_scores, virtual_pantry_state)
            for r in recipes
        ]

        scored = [s for s in scored if s["matched"] > 0]
        scored = [s for s in scored if s["missing"] <= max_missing]
        scored = [s for s in scored if s["score"] > 0]

        ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

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
    
    def _apply_recipe_to_virtual_state(self, recipe: Recipe, state: list):
        """
        Consume ingredients from the virtual pantry FEFO-style.
        `state` is a LIST of pantry-item dicts:
        [
            {"product_id": 141, "amount": 12, "expiration_date": date},
            {"product_id": 141, "amount": 12, "expiration_date": date},
            ...
        ]
        """
        # Make copy so original is not mutated
        new_state = [item.copy() for item in state]

        for ing in recipe.ingredients:
            pid = ing.matched_product_id
            required = ing.pantry_amount or 0
            if not pid or required <= 0:
                continue

            # FEFO items for this product
            items = [it for it in new_state if it["product_id"] == pid]

            # Sort FEFO (earliest expiration first)
            items.sort(key=lambda it: it["expiration_date"] or datetime.max)

            for item in items:
                if required <= 0:
                    break

                available = item["amount"]
                if available <= 0:
                    continue

                used = min(available, required)
                item["amount"] -= used
                required -= used

        # Filter out zero-amount items (optional)
        new_state = [it for it in new_state if it["amount"] > 0]

        return new_state

    def _compute_waste_score(self, item):
        """
        Returns per-unit waste urgency score.
        NOT multiplied by quantity.
        """

        exp = item.get("expiration_date")
        amt = item.get("amount", 0)

        if not exp or amt <= 0:
            return 0
        
        delta = exp - datetime.now()
        seconds_remaining = delta.total_seconds()

        if seconds_remaining <= 0:
            return 0

        product = (
            self.session.query(TJInventory)
            .filter_by(product_id=item["product_id"])
            .first()
        )
        category = (product.sub_category or product.category or "").lower()
        mult = CATEGORY_MULTIPLIERS.get(category, CATEGORY_MULTIPLIERS["other"])

        hours_remaining = seconds_remaining / 3600
        urgency = 1 / (hours_remaining)

        return urgency * mult
    
    def normalize_category_label(self, recipe: Recipe):
        """Return a clean category label to display on tiles."""
        if not recipe.category:
            return "Uncategorized"
        return recipe.category