from sqlalchemy import create_engine
from database.tables import create_all_tables
from database.config import DB_FILE, DATABASE_URL

def create_database():
    if DB_FILE.exists():
        print(f"Database already exists at {DB_FILE}")
        return

    engine = create_engine(DATABASE_URL, echo=False)
    create_all_tables(engine)
    print(f"Database created at {DB_FILE}")


if __name__ == "__main__":
    create_database()
