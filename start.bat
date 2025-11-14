@echo off
REM 1. Create virtual environment
python -m venv venv

REM 2. Activate virtual environment
call venv\Scripts\activate

REM 3. Upgrade pip
python -m pip install --upgrade pip

REM 4. Install dependencies
pip install -r requirements.txt

REM 5. Initialize database
python -m setup.init_db

REM 6. Run Streamlit app
streamlit run app\streamlit_app.py

pause