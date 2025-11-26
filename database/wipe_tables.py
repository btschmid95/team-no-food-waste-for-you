from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))
from database.config import DATABASE_URL

print("DATABASE_URL =", DATABASE_URL)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

TABLES_TO_CLEAR = [
    "ingredient_parse_meta",
    "pantry_event",
    "pantry",
    "ingredient",
    "recipe_selected",
    "recipe_recommended",
    "recipe",
    "tj_inventory",
]

def show_counts(session):
    print("\nRow counts:")
    for table in TABLES_TO_CLEAR:
        try:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table};")).scalar()
            print(f"  {table}: {count}")
        except Exception as e:
            print(f"  {table}: ERROR ({e})")
    print()

def wipe_tables():
    session = Session()

    try:
        print("\n=== BEFORE DELETE ===")
        show_counts(session)

        session.execute(text("PRAGMA foreign_keys = OFF;"))

        for table in TABLES_TO_CLEAR:
            print(f"Clearing: {table}")
            session.execute(text(f"DELETE FROM {table};"))

        try:
            session.execute(text("DELETE FROM sqlite_sequence;"))
        except Exception as e:
            print("Skipping sqlite_sequence reset:", e)

        session.commit()

        print("\n=== AFTER DELETE ===")
        show_counts(session)

    except Exception as e:
        session.rollback()
        print(f"Error during wipe: {e}")

    finally:
        try:
            session.execute(text("PRAGMA foreign_keys = ON;"))
        except Exception:
            pass
        session.close()




if __name__ == "__main__":
    #wipe_tables()
    from pprint import pprint
    from database.tables import RecipeSelected, Recipe
    session = Session()
    rows = session.query(RecipeSelected).all()

    print("RECIPE_SELECTED ROWS:", len(rows))
    for r in rows:
        print(
            r.sel_id,
            r.recipe_id,
            "planned:", r.planned_for,
            "slot:", r.meal_slot,
            "exists:", bool(session.query(Recipe).get(r.recipe_id))
        )