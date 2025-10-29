import sqlite3
from pathlib import Path
from tables import TABLE_DEFINITIONS

DB_FILE = Path("team-no-food-waste-for-you.sqlite")
SQL_FILE = Path("setup/tables.sql")

# def create_database():
#     if DB_FILE.exists():
#         print(f"Database already exists at {DB_FILE}")
#         return

#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()

#     # Example table
#     sql = SQL_FILE.read_text()
#     cursor.executescript(sql)

#     conn.commit()
#     conn.close()
#     print(f"Database created at {DB_FILE}")
def create_database():
    if DB_FILE.exists():
        print(f"Database already exists at {DB_FILE}")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for table_name, create_sql in TABLE_DEFINITIONS.items():
        cursor.execute(create_sql)
        print(f"Table '{table_name}' created.")

    conn.commit()
    conn.close()
    print(f"Database created at {DB_FILE}")

if __name__ == "__main__":
    create_database()