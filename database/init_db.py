## Code for database structure and archetecture was developed with assistence using Chat-GPT for structure, logic, and consistency ## 

from sqlalchemy import create_engine
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
    
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
