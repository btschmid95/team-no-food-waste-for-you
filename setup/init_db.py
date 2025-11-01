import sqlite3
from pathlib import Path

DB_FILE = Path("team-no-food-waste-for-you.sqlite")

def create_database():
    if DB_FILE.exists():
        print(f"Database already exists at {DB_FILE}")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Example table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL
    )
    """)

    conn.commit()
    conn.close()
    print(f"Database created at {DB_FILE}")

if __name__ == "__main__":
    create_database()