@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM 0. CHECK PYTHON IS INSTALLED
REM ============================================================
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python and try again.
    exit /b 1
)

REM ============================================================
REM 1. CHECK IF SETUP HAS ALREADY BEEN COMPLETED
REM ============================================================
IF EXIST setup_complete.flag (
    echo Setup already completed. Skipping initialization...
    GOTO run_app
)

echo Running first-time setup...

REM ============================================================
REM 2. CREATE VIRTUAL ENVIRONMENT
REM ============================================================
echo Creating virtual environment...
python -m venv venv
IF ERRORLEVEL 1 (
    echo [ERROR] Failed to create virtual environment.
    echo Setup aborted.
    exit /b 1
)

REM ============================================================
REM 3. ACTIVATE VIRTUAL ENVIRONMENT
REM ============================================================
call venv\Scripts\activate
IF ERRORLEVEL 1 (
    echo [ERROR] Failed to activate virtual environment.
    echo Setup aborted.
    exit /b 1
)

REM ============================================================
REM 4. INSTALL DEPENDENCIES
REM ============================================================
echo Upgrading pip...
python -m pip install --upgrade pip
IF ERRORLEVEL 1 (
    echo [ERROR] Pip upgrade failed.
    echo Setup aborted.
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt
IF ERRORLEVEL 1 (
    echo [ERROR] Dependency installation failed.
    echo Setup aborted.
    exit /b 1
)

REM ============================================================
REM 5. RUN SETUP SCRIPTS
REM ============================================================

echo Running database initialization...
python database\init_db.py
IF ERRORLEVEL 1 GOTO setup_fail

echo Running web scraping pipeline...
python data\pipeline\webscrape_to_database.py
IF ERRORLEVEL 1 GOTO setup_fail

echo Running ingredient parsing pipeline...
python data\pipeline\ingredient_parser_pipe.py
IF ERRORLEVEL 1 GOTO setup_fail

echo Running mapped ingredients population...
python data\pipeline\populate_mapped_ingredients.py
IF ERRORLEVEL 1 GOTO setup_fail

echo Running unit conversion pipeline...
python data\pipeline\unit_conversion_pipe.py
IF ERRORLEVEL 1 GOTO setup_fail

REM ============================================================
REM 6. MARK SETUP COMPLETE
REM ============================================================
echo Setup completed successfully.
echo success > setup_complete.flag
GOTO run_app


REM ============================================================
REM FAILURE HANDLER — DOES **NOT** WRITE FLAG
REM ============================================================
:setup_fail
echo.
echo [ERROR] A setup step failed.
echo The system will NOT mark setup as complete.
echo Fix the issue and re-run this script.
exit /b 1



REM ============================================================
REM 7. RUN APP (Normal Flow)
REM ============================================================
:run_app
echo Launching app...

call venv\Scripts\activate
IF ERRORLEVEL 1 (
    echo [ERROR] Could not activate virtual environment.
    exit /b 1
)

REM Correct streamlit path
streamlit run streamlit_app\streamlit_app.py

pause
