import streamlit as st

# Sidebar menu

st.title("Home")
st.write("Welcome to your Streamlit app!")

import streamlit as st
import sqlite3
from pathlib import Path

DB_FILE = Path("../my_local_db.sqlite")

def get_connection():
    return sqlite3.connect(DB_FILE)

st.title("My Local Streamlit App")

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

st.write("Tables in DB:", tables)