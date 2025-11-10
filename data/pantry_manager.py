import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..setup.tables import UsableIngredient, Cookbook, Pantry, TJInventory


engine = create_engine('../testing/cookbook.db')
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
            return f"Error: Ingreident {ingredient} not found"
        
        if pantry_item:
            # Item exists - add to existing amount
            pantry_item.amount = (pantry_item.amount or 0) + amount
            message = f"Added {amount} {unit} to existing {ingredient.norm_name} (now {pantry_item.amount} {unit})"
        else:
            # Item doesn't exist - create new entry
            date_purchased = datetime.now().isoformat()             # Or have user enter date?
            new_pantry_item = Pantry(
                ingredient_id = ingredient_id,
                amount = amount,
                unit = unit,
                date_purchased = date_purchased
            )
            self.session.add(new_pantry_item)
            message = f"Added {amount} {unit} of {ingredient_name}"
        
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
        
        return f"Pantry item with ID {ingredient_id} not found"


    def add_recipe_items(self, recipe_id):
        """
        Check if ingredients are in pantry first. If ingredient is not there, or not enough of it, add 
        ingredient to pantry. 
        """

        cookbook_entries = self.session.query(Cookbook).filter(Cookbook.recipe_id == recipe_id).all()

        added_items = []
        for entry in cookbook_entries:
            # Check if ingredient already exists in pantry with sufficient amount
            pantry_item = self.session.query(Pantry).filter(Pantry.ingredient_id == entry.ingredient_id).first()
            
            has_enough = pantry_item and pantry_item.amount >= entry.amount_id
            
            if not has_enough:
                # Either don't have it, or don't have enough - get from TJ inventory
                tj_product = self.session.query(TJInventory).join(
                    TJInventory.ingredients
                ).filter(
                    UsableIngredient.ingredient_id == entry.ingredient_id
                ).first()
                
                if tj_product:
                    if pantry_item:
                        # Add to existing pantry item
                        pantry_item.amount = (pantry_item.amount or 0) + tj_product.amount_id
                    else:
                        # Create new pantry item
                        date_purchased = datetime.now().isoformat()
                        pantry_item = Pantry(
                            ingredient_id = entry.ingredient_id,
                            amount = tj_product.amount_id,
                            unit = tj_product.unit,
                            date_purchased = date_purchased
                        )
                        self.session.add(pantry_item)
                    
                    added_items.append({
                        'ingredient_name': entry.ingredient.norm_name,
                        'tj_product': tj_product.name,
                        'amount_added': tj_product.amount_id,
                        'unit': tj_product.unit
                    })

        self.session.commit()
        
        return f"Updated {added_items}"


    def update_recipe_items(self, recipe_id):
        """ 
        Remove amounts of all ingredients for a recipe from the pantry.
        """

        cookbook_entries = self.session.query(Cookbook).filter(Cookbook.recipe_id == recipe_id).all()

        updated_items = []
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

                else:
                    # Still some left - update the amount
                    pantry_item.amount = new_amount
                    updated_items.append({
                        'ingredient_name': entry.ingredient.norm_name,
                        'amount_removed': entry.amount_id,
                        'unit': entry.unit,
                    })
        
        self.session.commit()

        return f"Updated {updated_items}"