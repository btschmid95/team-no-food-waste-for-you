import streamlit as st
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from pathlib import Path
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from database.config import DATABASE_URL

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL)

@st.cache_resource
def get_sessionmaker():
    return sessionmaker(bind=get_engine())

def get_session():
    return get_sessionmaker()()