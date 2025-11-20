import pandas as pd
from datetime import datetime, timedelta
import math
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..database.tables import Ingredient, PantryItem, TJInventory
from database.config import DATABASE_URL
from sqlalchemy import create_engine

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind = engine)
session = Session()

class PantryManager:
    def __init__(self, session):
        self.session = session


    def add_item(self, product_id, amount, unit):
        """
        Adds a single item to pantry. Each item is tracked separately for expiration tracking.
        """

        tj_product = self.session.query(TJInventory).filter(TJInventory.product_id == product_id).first()

        if not tj_product:
            return f"Error: Product {product_id} not found"

        date_added = datetime.now()
        expiration_date = date_added + timedelta(days = tj_product.shelf_life_days)

        new_pantry_item = PantryItem(
            product_id = product_id,
            amount = amount,
            unit = unit,
            date_added = date_added.isoformat(),
            expiration_date = expiration_date.isoformat()
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
            # Check if ingredient already exists in pantry with sufficient amount
            pantry_items = self.session.query(PantryItem).filter(PantryItem.product_id == ingredient.matched_product_id).all()
            
            current_amount = sum(item.amount for item in pantry_items) if pantry_items else 0
            has_enough = current_amount >= ingredient.amount
            
            if not has_enough:
                # Calculate how much more we need
                needed_amount = ingredient.amount - current_amount

                # Get product from TJ inventory
                tj_product = self.session.query(TJInventory).filter(TJInventory.product_id == ingredient.matched_product_id).first()

                if tj_product:
                    grocery_item = {
                        'ingredient_name': ingredient.norm_name,
                        'product_name': tj_product.name,
                        'amount': ingredient.amount_id,
                        'unit': ingredient.unit,
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
                    'amount': item['amount'],  # Amount per product
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
                'amount': item['amount'],
                'unit': item['unit'],
                'quantity': quantity,
                'total_needed': item['total_needed']
            })
        
        return combined_grocery_list
    

    def add_grocery_list(self, grocery_list):
        """
        Add items from grocery list to pantry. Each package of an item is tracked separately for expiration purposes.
        """

        messages = []
        for item in grocery_list:
            total_amount = item['quantity'] * item['amount']
            
            ingredient = self.session.query(Ingredient).filter(Ingredient.norm_name == item['ingredient_name']).first()
            
            if not ingredient:
                messages.append(f"Warning: Could not find ingredient {item['ingredient_name']}")
                continue
            
            # Get TJ product for shelf life
            tj_product = self.session.query(TJInventory).filter(TJInventory.product_id == ingredient.matched_product_id).first()

            if not tj_product:
                messages.append(f"Warning: Could not find TJ product for {item['ingredient_name']}")
                continue

            # Create separate pantry entries for each package
            for i in range(item['quantity']):
                date_purchased = datetime.now()
                expiration_date = date_purchased + timedelta(days = tj_product.shelf_life_days)

                pantry_item = PantryItem(
                    ingredient_id = ingredient.id,
                    amount = item['amount'],
                    unit = item['unit'],
                    date_purchased = date_purchased.isoformat(),
                    expiration_date = expiration_date.isoformat()
                )
                self.session.add(pantry_item)
                message = f"Added {item['quantity']} package(s) of {item['product_name']} ({item['amount']} {item['unit']} each)"
            
            messages.append(message)
        
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
            if not ingredient.matched_product_id:
                messages.append(f"Warning: No product matched for {ingredient.norm_name}")
                continue

            pantry_items = self.session.query(PantryItem).filter(
                PantryItem.product_id == ingredient.matched_product_id
            ).order_by(PantryItem.expiration_date).all()
            
            if not pantry_items:
                messages.append(f"Warning: {ingredient.norm_name} not found in pantry")
                continue
            
            amount_needed = ingredient.amount
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
        """
        
        pantry_items = self.session.query(PantryItem).all()
        
        items_data = []
        for pantry_item in pantry_items:
            tj_product = self.session.query(TJInventory).filter(TJInventory.product_id == pantry_item.product_id).first()
            
            if tj_product:
                item_info = {
                    'pantry_id': pantry_item.pantry_id,
                    'product_id': pantry_item.product_id,
                    'product_name': tj_product.name,
                    'amount': pantry_item.amount,
                    'unit': pantry_item.unit,
                    'date_added': pantry_item.date_added,
                    'expiration_date': pantry_item.expiration_date
                }
                items_data.append(item_info)
        
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
        

