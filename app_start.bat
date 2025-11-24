@echo off
setlocal

REM === 1. Check if setup has been run ===
IF EXIST setup_complete.flag (
    echo Setup already completed. Skipping initialization...
    GOTO run_app
)

echo Running first-time setup...

REM === 2. Create virtual environment ===
python -m venv venv

REM === 3. Activate virtual environment ===
call venv\Scripts\activate

REM === 4. Install dependencies ===
python -m pip install --upgrade pip
pip install -r requirements.txt

REM === 5. Run initial setup scripts ===
python database\init_db.py
python data\pipeline\webscrape_to_database.py
python data\pipeline\ingredient_parser_pipe.py
python data\pipeline\run_product_mapping_pipe.py
python data\pipeline\populate_mapped_ingredients.py
python data\pipeline\unit_conversion_pipe.py

REM === 6. Mark setup complete ===
echo Setup complete > setup_complete.flag

echo First-time setup complete. Launching app...

:run_app
REM === 7. Activate virtual environment ===
call venv\Scripts\activate

REM === 8. Run Streamlit app (✔ corrected path)
streamlit run streamlit_app\streamlit_app.py

pause
