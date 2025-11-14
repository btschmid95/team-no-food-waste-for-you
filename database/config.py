from pathlib import Path

# Project root (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parents[1]

# Database file location
DB_FILE = BASE_DIR / "database" / "team-no-food-waste-for-you.sqlite"

# SQLAlchemy-compatible database URL
DATABASE_URL = f"sqlite:///{DB_FILE}"