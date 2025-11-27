import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repo's root directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from database.tables import Ingredient, PantryItem, TJInventory, PantryEvent, RecipeSelected, Recipe
from database.config import DATABASE_URL
from sqlalchemy import create_engine

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind = engine)
session = Session()



class PantryManager:
    def __init__(self, session):
        self.session = session


    def add_item(self, product_id, amount, unit, planned_date = None):
        """
        Adds a single item to pantry. Each item is tracked separately for expiration tracking.
        """

        tj_product = self.session.query(TJInventory).filter(TJInventory.product_id == product_id).first()

        if not tj_product:
            return f"Error: Product {product_id} not found"
        planned_date = None
        if planned_date:
            # planned_date might be a date; normalize to datetime
            if isinstance(planned_date, datetime):
                date_purchased = planned_date
            else:
                date_purchased = datetime.combine(planned_date, datetime.min.time())
        else:
            date_purchased = datetime.now()

        expiration_date = date_purchased + timedelta(days = tj_product.shelf_life_days)

        new_pantry_item = PantryItem(
            product_id = product_id,
            amount = amount,
            unit = unit,
            date_added = date_purchased,
            expiration_date = expiration_date
        )
        self.session.add(new_pantry_item)
        message = f"Added {amount} {unit} of {tj_product.norm_name}"
        
        self.session.commit()
        
        return message

    def remove_item(self, pantry_id):
        """
        Remove a single item from pantry by pantry_id.
        Also removes planned recipes that require this ingredient.
        """

        pantry_item = (
            self.session.query(PantryItem)
            .filter(PantryItem.pantry_id == pantry_id)
            .first()
        )

        if not pantry_item:
            return f"Pantry item {pantry_id} not found"

        product_id = pantry_item.product_id

        # Delete pantry item
        self.session.delete(pantry_item)
        self.session.commit()

        # Remove related planned recipes
        removed_recipes = self.remove_related_planned_recipes(product_id)

        if removed_recipes:
            return (
                f"Removed product_id {product_id} from pantry. "
                f"Also removed {len(removed_recipes)} planned recipe(s)."
            )
        else:
            return f"Removed product_id {product_id} from pantry."


    def get_needed_recipe_items(self, recipe_id):
        """
        Check if ingredients are in pantry first. If ingredient is not there, or not enough of it, add 
        ingredient to grocery list. Return grocery list. 
        """

        ingredients = self.session.query(Ingredient).filter(Ingredient.recipe_id == recipe_id).all()

        grocery_list = []
        for ingredient in ingredients:
            pid = getattr(ingredient, "matched_product_id", None)
            needed = ingredient.pantry_amount
            if pid is None or needed is None:
                continue
            # Check if ingredient already exists in pantry with sufficient amount
            pantry_items = self.session.query(PantryItem).filter(PantryItem.product_id == ingredient.matched_product_id).all()
            
            current_amount = sum(
                item.amount for item in pantry_items
                if item.expiration_date >= datetime.now()
            )
            has_enough = current_amount >= ingredient.pantry_amount

            if not has_enough:
                # Calculate how much more we need
                needed_amount = ingredient.pantry_amount - current_amount

                # Get product from TJ inventory
                tj_product = self.session.query(TJInventory).filter(TJInventory.product_id == ingredient.matched_product_id).first()

                if tj_product:
                    grocery_item = {
                        'ingredient_name': ingredient.norm_name,
                        'product_name': tj_product.name,
                        'product_id': ingredient.matched_product_id,
                        'amount': tj_product.quantity,      
                        'unit': tj_product.unit,  
                        'needed_amount': needed_amount
                    }
                    grocery_list.append(grocery_item)
                
        return grocery_list
    

    def get_grocery_list(self, recipe_id_list):
        """
        Get combined grocery list for multiple recipes, combining duplicate products and only buying what's needed.
        """

        all_items = []
        for recipe_id in recipe_id_list:
            items = self.get_needed_recipe_items(recipe_id)
            all_items.extend(items)

        # Combine duplicates by product name, summing needed amounts
        combined_items = {}
        for item in all_items:
            product_name = item['product_name']
            
            if product_name in combined_items:
                # Product already in list, add to needed amount
                combined_items[product_name]['total_needed'] += item['needed_amount']
            else:
                # New product, add to combined list
                combined_items[product_name] = {
                    'ingredient_name': item['ingredient_name'],
                    'product_name': item['product_name'],
                    'product_id': item['product_id'],      # ✅ keep product_id
                    'amount': item['amount'],              # Amount per product
                    'unit': item['unit'],
                    'total_needed': item['needed_amount']
                }

        
        # Calculate combined grocery list
        combined_grocery_list = []
        for item in combined_items.values():        
            quantity = math.ceil(item['total_needed'] / item['amount'])
            
            combined_grocery_list.append({
                'ingredient_name': item['ingredient_name'],
                'product_name': item['product_name'],
                'product_id': item['product_id'],
                'amount': item['amount'],
                'unit': item['unit'],
                'quantity': quantity,
                'total_needed': item['total_needed']
            })
        
        return combined_grocery_list
    

    def add_grocery_list(self, grocery_list, planned_date=None):
        """
        Add items from grocery list to pantry. Each package of an item is tracked
        separately for expiration purposes, using the planned_date as the purchase
        date (if provided).
        """

        messages = []

        for item in grocery_list:
            product_id = item["product_id"]
            amount_per_package = item["amount"]   # how much 1 unit contributes
            unit = item["unit"]
            qty = item["quantity"]

            # Look up the Trader Joe's product directly by product_id
            tj_product = (
                self.session.query(TJInventory)
                .filter(TJInventory.product_id == product_id)
                .first()
            )

            if not tj_product:
                messages.append(
                    f"Warning: Could not find TJ product for product_id {product_id} "
                    f"({item.get('product_name', 'Unknown')})"
                )
                continue

            # Purchase date = planned_date if provided, else "now"
            planned_date = None # note to self, update this in the future to account for a "shopping list"
            if planned_date:
                if isinstance(planned_date, datetime):
                    date_purchased = planned_date
                else:
                    date_purchased = datetime.combine(planned_date, datetime.min.time())
            else:
                date_purchased = datetime.now()

            # Expiration date based on shelf life
            shelf_days = tj_product.shelf_life_days or 0
            expiration_date = date_purchased + timedelta(days=shelf_days)

            for _ in range(qty):
                pantry_item = PantryItem(
                    product_id=product_id,
                    amount=amount_per_package,
                    unit=unit,
                    date_added=date_purchased,
                    expiration_date=expiration_date,
                )
                self.session.add(pantry_item)

            messages.append(
                f"Added {qty} package(s) of {tj_product.name} "
                f"({amount_per_package} {unit} each)"
            )
            print(messages)
        self.session.commit()
        return messages


    def delete_recipe_items(self, recipe_id):
        """ 
        Remove amounts of all ingredients for a recipe from the pantry. Use oldest items first (first in, first out based on
        expiration date).
        """

        ingredients = self.session.query(Ingredient).filter(Ingredient.recipe_id == recipe_id).all()

        messages = []
        for ingredient in ingredients:
            if ingredient.matched_product_id is None or ingredient.pantry_amount is None:
                messages.append(f"Warning: No product matched for {ingredient.norm_name}")
                continue

            pantry_items = self.session.query(PantryItem).filter(
                PantryItem.product_id == ingredient.matched_product_id
            ).order_by(PantryItem.expiration_date).all()
            
            if not pantry_items:
                messages.append(f"Warning: {ingredient.norm_name} not found in pantry")
                continue
            
            amount_needed = ingredient.pantry_amount
            items_used = []
            
            # Use items starting with oldest (earliest expiration)
            for pantry_item in pantry_items:
                if amount_needed <= 0:
                    break
                
                if pantry_item.amount <= amount_needed:
                    # Use entire item
                    amount_needed -= pantry_item.amount
                    items_used.append(pantry_item.amount)
                    self.session.delete(pantry_item)
                else:
                    # Use partial amount
                    pantry_item.amount -= amount_needed
                    items_used.append(amount_needed)
                    amount_needed = 0
            
            total_used = sum(items_used)
            message = f"Removed {total_used} {ingredient.unit} of {ingredient.norm_name} ({len(items_used)} package(s))"
            messages.append(message)
        
        self.session.commit()

        return "\n".join(messages)
    

    def get_pantry_items(self):
        """
        Get all items currently in the pantry as a DataFrame.
        Includes category + subcategory for filtering and visualizations.
        """

        pantry_items = self.session.query(PantryItem).all()

        items_data = []
        for pantry_item in pantry_items:
            tj_product = (
                self.session.query(TJInventory)
                .filter(TJInventory.product_id == pantry_item.product_id)
                .first()
            )

            if tj_product:
                items_data.append({
                    'pantry_id': pantry_item.pantry_id,
                    'product_id': pantry_item.product_id,
                    'product_name': tj_product.name,
                    'category': tj_product.category,
                    'sub_category': tj_product.sub_category,
                    'amount': pantry_item.amount,
                    'unit': pantry_item.unit,
                    'date_added': pantry_item.date_added,
                    'expiration_date': pantry_item.expiration_date
                })

        return pd.DataFrame(items_data)
    

    def get_expiring_soonest(self):
        """
        Get the pantry item that is closest to expiring. Returns a dictionary with item details, or None if pantry is empty.
        """

        
        pantry_item = self.session.query(PantryItem).order_by(
            PantryItem.expiration_date
        ).first()
        
        if not pantry_item:
            return None
        
        tj_product = self.session.query(TJInventory).filter(
            TJInventory.product_id == pantry_item.product_id
        ).first()
        
        item_info = {
            'pantry_id': pantry_item.pantry_id,
            'product_id': pantry_item.product_id,
            'product_name': tj_product.name if tj_product else 'Unknown',
            'norm_name': tj_product.norm_name if tj_product else 'Unknown',
            'amount': pantry_item.amount,
            'unit': pantry_item.unit,
            'date_added': pantry_item.date_added,
            'expiration_date': pantry_item.expiration_date
        }
        
        return item_info
    
    def get_all_items(self):
        """
        Return pantry items in list-of-dict format for the recommender.
        """
        df = self.get_pantry_items()
        if df.empty:
            return []

        return [
            {
                "product_id": row.product_id,
                "amount": row.amount,
                "expiration_date": row.expiration_date
            }
            for _, row in df.iterrows()
        ]
    
    def import_state(self, virtual_state: list):
        """
        Convert virtual pantry list-of-dicts into the format used by the recommender.
        Accepts a list of pantry-item dicts.
        """
        items = []
        for it in virtual_state:
            items.append({
                "product_id": it["product_id"],
                "amount": it["amount"],
                "expiration_date": it["expiration_date"],
            })
        return items
    
    def consume_recipe(self, recipe_id: int, sel_id: int):
        """
        Consume pantry items FIFO/FEFO for a recipe.
        Logs PantryEvent(event_type='consume') for each usage.
        """

        ingredients = (
            self.session.query(Ingredient)
            .filter(Ingredient.recipe_id == recipe_id)
            .all()
        )

        for ing in ingredients:
            if not ing.matched_product_id:
                continue

            needed = ing.pantry_amount
            if needed is None or needed <= 0:
                continue

            pantry_items = (
                self.session.query(PantryItem)
                .filter(PantryItem.product_id == ing.matched_product_id)
                .order_by(PantryItem.expiration_date.asc())  # FEFO
                .all()
            )

            for pi in pantry_items:
                if needed <= 0:
                    break

                used = min(pi.amount, needed)
                needed -= used


                expiring_soon = (
                    pi.expiration_date.date() - datetime.now().date()
                ) <= timedelta(days=2)

                if expiring_soon:
                    # Log avoided waste event
                    avoid_event = PantryEvent(
                        pantry_id=pi.pantry_id,
                        event_type="avoid",   # <-- new event type
                        amount=used,
                        unit=pi.unit,
                        recipe_selection_id=sel_id
                    )
                    self.session.add(avoid_event)

                # Log event
                event = PantryEvent(
                    pantry_id=pi.pantry_id,
                    event_type="consume",
                    amount=used,
                    unit=pi.unit,
                    recipe_selection_id=sel_id
                )
                self.session.add(event)

                # Remove or update PantryItem
                if used == pi.amount:
                    self.session.delete(pi)
                else:
                    pi.amount -= used

        self.session.commit()

    def clear_pantry(self):
        """
        Completely reset pantry state:
        - Delete ALL pantry items
        - Delete ALL planned recipes
        - Delete ALL pantry events (consume, trash, avoid)
        """

        messages = []

        # 1. Delete all events FIRST (to avoid FK issues)
        events = self.session.query(PantryEvent).all()
        num_events = len(events)
        for ev in events:
            self.session.delete(ev)
        messages.append(f"Deleted {num_events} pantry events.")

        # 2. Delete pantry items
        pantry_items = self.session.query(PantryItem).all()
        num_items = len(pantry_items)
        for pi in pantry_items:
            self.session.delete(pi)
        messages.append(f"Deleted {num_items} pantry items.")

        # 3. Delete planned recipes
        planned = self.session.query(RecipeSelected).all()
        num_planned = len(planned)
        for p in planned:
            self.session.delete(p)
        messages.append(f"Deleted {num_planned} planned recipes.")

        self.session.commit()

        return messages
    
    def trash_pantry(self, category=None):
        """
        Throw away all pantry items, OR only items of a given category.
        Logs PantryEvent(event_type='trash') for each removal.
        """

        messages = []

        q = self.session.query(PantryItem).join(TJInventory)
        if category:
            q = q.filter(TJInventory.category == category)

        items = q.all()

        for pi in items:
            # Log the trash event
            event = PantryEvent(
                pantry_id=pi.pantry_id,
                event_type="trash",
                amount=pi.amount,
                unit=pi.unit,
                recipe_selection_id=None
            )
            self.session.add(event)

            self.session.delete(pi)

            messages.append(
                f"Trashed {pi.amount} {pi.unit} of product_id={pi.product_id}"
            )

        self.session.commit()

        if category:
            messages.append(f"All items in category '{category}' trashed.")
        else:
            messages.append("All pantry items trashed.")

        return messages


    def trash_expired_items(self):
        now = datetime.now()   # precise timestamp
        messages = []

        expired_items = (
            self.session.query(PantryItem)
            .filter(PantryItem.expiration_date < now)
            .all()
        )

        print("Now:", now)
        print("Expired:", [ (pi.pantry_id, pi.expiration_date) for pi in expired_items ])

        if not expired_items:
            return ["No expired items found."]

        for pi in expired_items:
            event = PantryEvent(
                pantry_id=pi.pantry_id,
                event_type="trash",
                amount=pi.amount,
                unit=pi.unit,
                recipe_selection_id=None
            )
            self.session.add(event)
            self.session.delete(pi)

        self.session.commit()

        return [f"Removed {len(expired_items)} expired item(s)."]



    def remove_related_planned_recipes(self, product_id):
        """
        Remove planned/confirmed recipes that rely on a specific pantry product.
        Returns the sel_id values of the removed recipes.
        """
        removed = []

        # Find all planned/confirmed recipes
        planned = self.session.query(RecipeSelected).all()

        for p in planned:
            rid = p.recipe_id
            ingredients = (
                self.session.query(Ingredient)
                .filter(Ingredient.recipe_id == rid)
                .all()
            )

            # Does this recipe rely on the removed product?
            for ing in ingredients:
                if ing.matched_product_id == product_id:
                    removed.append(p.sel_id)
                    self.session.delete(p)
                    break 

        if removed:
            self.session.commit()

        return removed
    
    def trash_item(self, pantry_id):
        """
        Trash a single pantry item.
        Logs a trash event and removes planned recipes depending on this product.
        """

        pantry_item = (
            self.session.query(PantryItem)
            .filter(PantryItem.pantry_id == pantry_id)
            .first()
        )

        if not pantry_item:
            return f"Pantry item {pantry_id} not found"

        product_id = pantry_item.product_id

        # Log trash event
        event = PantryEvent(
            pantry_id=pantry_item.pantry_id,
            event_type="trash",
            amount=pantry_item.amount,
            unit=pantry_item.unit,
            recipe_selection_id=None
        )
        self.session.add(event)

        # Remove pantry item
        self.session.delete(pantry_item)
        self.session.commit()

        # Remove any planned recipes that need this ingredient
        removed_recipes = self.remove_related_planned_recipes(product_id)

        if removed_recipes:
            return (
                f"Trashed product_id {product_id}. "
                f"Removed {len(removed_recipes)} dependent planned recipe(s)."
            )
        else:
            return f"Trashed product_id {product_id}."

    def generate_sample_pantry(self, seed: int = 42):

        rng = np.random.default_rng(seed)
        messages = []

        inv = pd.read_sql("SELECT * FROM tj_inventory", self.session.bind)

        # ------------------------------------------------------------
        # Precompute a product_id -> category map for quick lookups
        # ------------------------------------------------------------
        product_category = {
            int(row.product_id): row.category
            for _, row in inv[["product_id", "category"]].iterrows()
        }

        # ============================================================
        # 1. Pick THREE recipes: Breakfast, Lunch, Dinner
        #    Dinner is biased to contain a Meat/Seafood/Plant-based ingredient
        # ============================================================

        def pick_recipe_by_keyword(keyword, require_meat=False):
            """
            Pick a recipe whose Recipe.category contains `keyword`
            and that has at least one matched ingredient.

            If require_meat=True, prefer recipes that have at least one
            ingredient whose product category == 'Meat, Seafood & Plant-based'.
            """
            q = (
                self.session.query(Recipe)
                .filter(Recipe.category.ilike(f"%{keyword}%"))
                .join(Ingredient)
                .filter(Ingredient.matched_product_id != None)
            )
            recipes = q.all()
            if not recipes:
                return None

            if not require_meat:
                # Just return the first matching recipe (or you could randomize)
                return recipes[0]

            # Prefer recipes that actually use a meat/seafood/plant-based product
            meat_recipes = []
            for r in recipes:
                for ing in r.ingredients:
                    pid = getattr(ing, "matched_product_id", None)
                    if pid and product_category.get(int(pid)) == "Meat, Seafood & Plant-based":
                        meat_recipes.append(r)
                        break

            if meat_recipes:
                return meat_recipes[0]   # or random choice if you like
            else:
                # Fallback: no meat-using recipe found in this category
                return recipes[0]

        breakfast_recipe = pick_recipe_by_keyword("breakfast")
        lunch_recipe     = pick_recipe_by_keyword("lunch")
        # 👇 Dinner is *required* to use a meat/seafood/plant-based product if possible
        dinner_recipe    = pick_recipe_by_keyword("dinner", require_meat=True)

        recipes = [r for r in [breakfast_recipe, lunch_recipe, dinner_recipe] if r]

        if not recipes:
            return ["ERROR: No breakfast/lunch/dinner recipes exist with mapped ingredients."]

        for r in recipes:
            messages.append(f"Chosen recipe: {r.title}")

        # ============================================================
        # Collect all recipe ingredient product_ids
        # ============================================================

        all_recipe_ing_ids = set()
        for r in recipes:
            for ing in r.ingredients:
                if ing.matched_product_id:
                    all_recipe_ing_ids.add(int(ing.matched_product_id))

        # ============================================================
        # 2. Add TWO expired items NOT used in ANY recipe
        # ============================================================

        expired_candidates = inv[~inv["product_id"].isin(all_recipe_ing_ids)]

        if expired_candidates.empty:
            return ["ERROR: No non-recipe items available to create expired test items"]

        expired_sample = expired_candidates.head(2)

        for _, row in expired_sample.iterrows():
            expiration = datetime.now() - timedelta(hours=12)
            date_added = datetime.now() - timedelta(days=2, hours=12)

            self.session.add(
                PantryItem(
                    product_id=row.product_id,
                    amount=row.quantity,
                    unit=row.unit,
                    date_added=date_added,
                    expiration_date=expiration,
                )
            )
            messages.append(
                f"Added EXPIRED test item '{row['name']}' (forced expired)"
            )

            # ============================================================
            # 3. Add recipe ingredients for ALL THREE RECIPES
            #    ALL will expire within 4–32 hours
            #    Ensure one Meat/Seafood ingredient is included (already handled)
            # ============================================================

            # Collect all ingredient objects for selected recipes
            all_ing_objs = []
            for recipe in recipes:
                ing_list = (
                    self.session.query(Ingredient)
                    .filter(Ingredient.recipe_id == recipe.recipe_id)
                    .all()
                )
                all_ing_objs.extend(ing_list)

            # Only keep mapped ingredients
            all_ing_objs = [ing for ing in all_ing_objs if ing.matched_product_id]

            # Identify meat-category ingredients
            meat_ing_objs = [
                ing for ing in all_ing_objs
                if product_category.get(int(ing.matched_product_id)) == "Meat, Seafood & Plant-based"
            ]

            # We will artificially expire EVERYTHING in this window
            def random_expiration():
                hours = int(rng.integers(4, 33))   # 4–32 hours
                return datetime.now() + timedelta(hours=hours), hours

            # Insert all recipe ingredients as pantry items
            for ing in all_ing_objs:
                pid = int(ing.matched_product_id)
                product = (
                    self.session.query(TJInventory)
                    .filter_by(product_id=pid)
                    .first()
                )
                if not product:
                    continue

                expiration, hrs = random_expiration()
                date_added = datetime.now() - timedelta(hours=int(rng.integers(0, 5)))

                self.session.add(
                    PantryItem(
                        product_id=product.product_id,
                        amount=product.quantity,
                        unit=product.unit,
                        date_added=date_added,
                        expiration_date=expiration,
                    )
                )

                messages.append(
                    f"Added RECIPE ingredient '{product.name}' — expires in {hrs}h"
                )
        # ============================================================
        # 4. Add random items (normal)
        # ============================================================

        def add_random_items(category_name, count):
            subset = inv[inv["category"] == category_name]
            if subset.empty:
                messages.append(f"WARNING: No items in '{category_name}'")
                return

            sample = subset.sample(n=min(count, len(subset)), random_state=seed)

            for _, row in sample.iterrows():
                hours_back = int(rng.integers(0, 49))
                date_added = datetime.now() - timedelta(hours=hours_back)
                expiration = date_added + timedelta(days=row.shelf_life_days)

                self.session.add(
                    PantryItem(
                        product_id=row.product_id,
                        amount=row.quantity,
                        unit=row.unit,
                        date_added=date_added,
                        expiration_date=expiration,
                    )
                )

                messages.append(
                    f"Added {category_name} item '{row['name']}' (added {hours_back}h ago)"
                )

        add_random_items("Fresh Fruits & Veggies", 10)
        add_random_items("Bakery", 4)
        add_random_items("For the Pantry", 4)
        add_random_items("From The Freezer", 5)
        add_random_items("Dairy & Eggs", 3)

        # ============================================================
        # 5. Add backdated items NOT used in any recipe
        # ============================================================

        def add_backdated_items(category_name, count):
            subset = inv[
                (inv["category"] == category_name)
                & (~inv["product_id"].isin(all_recipe_ing_ids))
            ]

            if subset.empty:
                messages.append(f"WARNING: No valid backdated '{category_name}' items")
                return

            sample = subset.sample(n=min(count, len(subset)), random_state=seed + 99)

            for _, row in sample.iterrows():
                hours_back = int(rng.integers(24, 73))
                date_added = datetime.now() - timedelta(hours=hours_back)
                expiration = date_added + timedelta(days=row.shelf_life_days)

                self.session.add(
                    PantryItem(
                        product_id=row.product_id,
                        amount=row.quantity,
                        unit=row.unit,
                        date_added=date_added,
                        expiration_date=expiration,
                    )
                )

                status = "(EXPIRED)" if expiration < datetime.now() else ""
                messages.append(
                    f"Added BACKDATED {category_name} item '{row['name']}' {status}"
                )

        add_backdated_items("Meat, Seafood & Plant-based", 2)
        add_backdated_items("Fresh Fruits & Veggies", 2)

        # ============================================================
        # 6. Commit
        # ============================================================

        self.session.commit()
        return messages


    
if __name__ == "__main__":
    pantry_ids = set(item.product_id for item in session.query(PantryItem).all())
    inventory_ids = set(item.product_id for item in session.query(TJInventory).all())

    missing = pantry_ids - inventory_ids

    print(len(missing), missing)

