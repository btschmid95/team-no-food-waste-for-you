import pandas as pd
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

from database.tables import Ingredient, PantryItem, TJInventory, PantryEvent, RecipeSelected
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
        Remove a single item from pantry by pantry_id. This deletes the entire pantry entry.
        """

        pantry_item = self.session.query(PantryItem).filter(PantryItem.pantry_id == pantry_id).first()

        if pantry_item:
            tj_product = self.session.query(TJInventory).filter(TJInventory.product_id == pantry_item.product_id).first()

            product_name = tj_product.norm_name

            self.session.delete(pantry_item)
            self.session.commit()

            return f"Removed {product_name}"
        
        return f"Pantry item {pantry_id} not found"


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
            
            current_amount = sum(item.amount for item in pantry_items) if pantry_items else 0
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
            if planned_date:
                # planned_date might be a date; normalize to datetime
                if isinstance(planned_date, datetime):
                    date_purchased = planned_date
                else:
                    date_purchased = datetime.combine(planned_date, datetime.min.time())
            else:
                date_purchased = datetime.now()

            # Expiration date based on shelf life
            shelf_days = tj_product.shelf_life_days or 0
            expiration_date = date_purchased + timedelta(days=shelf_days)

            # Create one PantryItem per "package"
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
    
    def import_state(self, virtual_state: dict):
        """
        Convert a virtual pantry dict into list-of-dicts format.
        """
        items = []
        for pid, data in virtual_state.items():
            items.append({
                "product_id": pid,
                "amount": data.get("amount", 0),
                "expiration_date": data.get("expiration_date")
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



if __name__ == "__main__":
    pantry_ids = set(item.product_id for item in session.query(PantryItem).all())
    inventory_ids = set(item.product_id for item in session.query(TJInventory).all())

    missing = pantry_ids - inventory_ids

    print(len(missing), missing)
