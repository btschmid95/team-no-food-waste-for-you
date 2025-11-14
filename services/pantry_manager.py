import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..database.tables import UsableIngredient, Cookbook, Pantry, TJInventory
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


    def add_recipe_items(self, recipe_id):
        """
        Check if ingredients are in pantry first. If ingredient is not there, or not enough of it, add 
        ingredient to pantry. 
        """

        cookbook_entries = self.session.query(Cookbook).filter(Cookbook.recipe_id == recipe_id).all()

        messages = []
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
                        message = f"Added {tj_product.amount_id} {tj_product.unit} of {entry.ingredient.norm_name} from {tj_product.name} (now {pantry_item.amount} {tj_product.unit})"
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
                        message = f"Added {tj_product.amount_id} {tj_product.unit} of {entry.ingredient.norm_name} from {tj_product.name} to pantry"
                    
                    messages.append(message)

        self.session.commit()
        
        return "\n".join(messages)


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