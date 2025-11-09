from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from tables import Base, TJInventory, Recipe, RawIngredient

DB_FILE = Path("team-no-food-waste-for-you.sqlite")
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)
Session = sessionmaker(bind=engine)

def see_tables():
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    print("Tables:", tables)

    for table in tables:
        print(f"\nTable: {table}")
        for column in inspector.get_columns(table):
            print(f"  {column['name']} ({column['type']})", end='')
            if column.get("primary_key"):
                print(" [PK]", end='')
            print()

def explore_tables(limit=5):
    """
    Prints the first `limit` rows of each table in the database.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    session = Session()
    
    print(f"Database tables: {tables}\n")
    
    for table_name in tables:
        print(f"--- {table_name} ---")
        
        if table_name == "tj_inventory":
            rows = session.query(TJInventory).limit(limit).all()
            for row in rows:
                print(f"id={row.product_id}, name={row.name}, norm_name={row.norm_name}, unit={row.unit}, price={row.price}, category={row.category}, url={row.url}")
                
        elif table_name == "recipe":
            rows = session.query(Recipe).limit(limit).all()
            for row in rows:
                print(f"id={row.recipe_id}, title={row.title}, category={row.category}, serves={row.serves}, time={row.time}, url={row.url}, image_url={row.image_url}")
                
        elif table_name == "raw_ingredients":
            rows = session.query(RawIngredient).limit(limit).all()
            for row in rows:
                print(f"id={row.raw_ing_id}, recipe_id={row.recipe_id}, raw_text={row.raw_text}")
                
        else:
            print(f"Table {table_name} exists but is not mapped to ORM classes.")
        
        print("\n")
    
    session.close()

if __name__ == "__main__":
    explore_tables(limit=5)
