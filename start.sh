#!/bin/bash

# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install dependencies
pip install -r requirements.txt

# 5. Initialize database
python setup/init_db.py

# 6. Run Streamlit app
streamlit run app/streamlit_app.py
