from pathlib import Path
from sqlalchemy import create_engine
from tables import create_all_tables

DB_FILE = Path("team-no-food-waste-for-you.sqlite")

def create_database():
    if DB_FILE.exists():
        print(f"Database already exists at {DB_FILE}")
        return

    engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)
    create_all_tables(engine)
    print(f"Database created at {DB_FILE}")

if __name__ == "__main__":
    create_database()