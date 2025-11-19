import pandas as pd
from datetime import datetime
import math
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..database.tables import Cookbook, Ingredient, Pantry, TJInventory, UsableIngredient, PantryItem
from database.config import DATABASE_URL
from sqlalchemy import create_engine

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind = engine)
session = Session()

class PantryManager:
    def __init__(self, session):
        self.session = session


    def add_item(self, ingredient_id, amount, unit):
        """
        Adds a single item to pantry. If item already exits, add to the existing amount.
        """
        # Check if item already exists in pantry
        pantry_item = self.session.query(Pantry).filter(Pantry.ingredient_id == ingredient_id).first()
        
        # Get ingredient name for return message
        ingredient = self.session.query(UsableIngredient).filter(UsableIngredient.ingredient_id == ingredient_id).first()
        if not ingredient:
            return f"Error: Ingredient {ingredient} not found"
        
        if pantry_item:
            # Item exists - add to existing amount
            pantry_item.amount = (pantry_item.amount or 0) + amount
            message = f"Added {amount} {unit} to existing {ingredient.norm_name} (now {pantry_item.amount} {unit})"
        else:
            # Item doesn't exist - create new entry
            date_purchased = datetime.now().isoformat()
            new_pantry_item = Pantry(
                ingredient_id = ingredient_id,
                amount = amount,
                unit = unit,
                date_purchased = date_purchased
            )
            self.session.add(new_pantry_item)
            message = f"Added {amount} {unit} of {ingredient}"
        
        self.session.commit()
        
        return message


    def remove_item(self, ingredient_id):
        """
        Remove a single item from pantry by pantry_id. This deletes the entire pantry entry.
        """

        pantry_item = self.session.query(Pantry).filter(Pantry.ingredient_id == ingredient_id).first()

        if pantry_item:
            ingredient_name = pantry_item.ingredient.norm_name
            self.session.delete(pantry_item)
            self.session.commit()

            return f"Removed {ingredient_name}"
        
        return f"Pantry item {ingredient_id} not found"


    def get_needed_recipe_items(self, recipe_id):
        """
        Check if ingredients are in pantry first. If ingredient is not there, or not enough of it, add 
        ingredient to grocery list. Return grocery list 
        """

        cookbook_entries = self.session.query(Cookbook).filter(Cookbook.recipe_id == recipe_id).all()

        grocery_list = []
        for entry in cookbook_entries:
            # Check if ingredient already exists in pantry with sufficient amount
            pantry_item = self.session.query(Pantry).filter(Pantry.ingredient_id == entry.ingredient_id).first()
            
            has_enough = pantry_item and pantry_item.amount >= entry.amount_id
            
            if not has_enough:
                # Calculate how much more we need
                current_amount = pantry_item.amount if pantry_item else 0
                needed_amount = entry.amount_id - current_amount

                # Either don't have it, or don't have enough - get from TJ inventory
                tj_product = self.session.query(TJInventory).join(
                    TJInventory.ingredients
                ).filter(
                    UsableIngredient.ingredient_id == entry.ingredient_id
                ).first()

                if tj_product:
                    grocery_item = {
                        'ingredient_name': entry.ingredient.norm_name,
                        'product_name': tj_product.name,
                        'amount': tj_product.amount_id,
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
        Add items from grocery list to pantry. If ingredient already exists in pantry, add to existing amount. If not,
        create new pantry entry.
        """

        messages = []
        for item in grocery_list:
            total_amount = item['quantity'] * item['amount']
            
            ingredient = self.session.query(Ingredient).filter(
                Ingredient.norm_name == item['ingredient_name']
            ).first()
            
            if not ingredient:
                messages.append(f"Warning: Could not find ingredient {item['ingredient_name']}")
                continue
            
            # Check if ingredient already exists in pantry
            pantry_item = self.session.query(Pantry).filter(
                Pantry.ingredient_id == ingredient.id
            ).first()
            
            if pantry_item:
                # Add to existing pantry item
                old_amount = pantry_item.amount
                pantry_item.amount += total_amount
                message = f"Updated {item['ingredient_name']}: {old_amount} → {pantry_item.amount} {item['unit']}"
            else:
                # Create new pantry item
                date_purchased = datetime.now().isoformat()
                pantry_item = Pantry(
                    ingredient_id = ingredient.id,
                    amount = total_amount,
                    unit = item['unit'],
                    date_purchased = date_purchased
                )
                self.session.add(pantry_item)
                message = f"Added {total_amount} {item['unit']} of {item['ingredient_name']} to pantry"
            
            messages.append(message)
        
        self.session.commit()
        
        return messages


    def delete_recipe_items(self, recipe_id):
        """ 
        Remove amounts of all ingredients for a recipe from the pantry.
        """

        cookbook_entries = self.session.query(Cookbook).filter(Cookbook.recipe_id == recipe_id).all()

        messages = []
        for entry in cookbook_entries:
            pantry_item = self.session.query(Pantry).filter(
                Pantry.ingredient_id == entry.ingredient_id
            ).first()
            
            if pantry_item and pantry_item.amount is not None:
                # Subtract the recipe amount from pantry
                new_amount = pantry_item.amount - entry.amount_id
                
                if new_amount == 0:
                    # Used it all up - delete the pantry entry
                    self.session.delete(pantry_item)
                    message = f"Removed all {entry.ingredient.norm_name} from pantry"

                else:
                    # Still some left - update the amount
                    pantry_item.amount = new_amount
                    message = f"Removed {entry.amount_id} {entry.unit} of {entry.ingredient.norm_name} (now {new_amount} {entry.unit})"

                messages.append(message)
        
        self.session.commit()

        return "\n".join(messages)
    
    def get_pantry_dataframe(self):
        items = (
            self.session.query(PantryItem)
            .join(TJInventory, PantryItem.product_id == TJInventory.product_id)
            .all()
        )

        rows = []
        for p in items:
            rows.append({
                "pantry_id": p.pantry_id,
                "product_id": p.product_id,
                "name": p.product.name,
                "category": p.product.category,
                "amount": p.amount,
                "unit": p.unit,
                "date_added": p.date_added,
                "expiration_date": p.expiration_date,
            })

        return pd.DataFrame(rows)
#class pantryManager:

#	def add_item_to_pantry() (add_item) (individual method for taking a product from tjinventory and adding it to the pantry)
#	def remove_item_from_pantry() (remove_item) (is this consume item?)
#	def consume_item() (individual method for consuming items. It removes it from the pantry. It updates the waste reduction tracker)
#	def get_most_oldest_item() (individual method for getting the oldest item from the pantry if there are quantities remaining)
#	def throw_away_item() () (individual method for updating the waste reduction tracker. removes item from the pantry. It updates the waste reduction tracker)
#	def add_recipe_items_to_pantry() (add_recipe_items) (takes in a selected recipe name, queries for the ingredients, queries for the products, checks quantities, "buys" products if necessary)
#	def remove_recipe_items_to_pantry() (delete_recipe_items) (takes in a selected recipe name, queries for the ingredients, queries for the products, deducts quantities based on "using" the recipe)
#	def queryPantry() # returns all of the items from the pantry