@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo STARTING SETUP (DEBUG MODE)
echo The window will NOT close on errors.
echo ============================================================
echo.

REM ============================================================
REM 0. CHECK PYTHON IS INSTALLED OR FIX PATH
REM ============================================================
setlocal EnableDelayedExpansion

echo Checking Python installation...
python --version >nul 2>&1

IF NOT ERRORLEVEL 1 (
    echo Python detected.
) ELSE (
    echo Python NOT found in PATH. Attempting auto-detection...

    set "PYTHON_DIR="

    for /d %%D in ("%LocalAppData%\Programs\Python\Python*") do (
        set "PYTHON_DIR=%%D"
    )

    echo Auto-detected: !PYTHON_DIR!

    if not defined PYTHON_DIR (
        echo Could not automatically detect python.
        echo Please enter the folder containing python.exe:
        set /p PYTHON_DIR="Python install path: "
    )

    if exist "!PYTHON_DIR!\python.exe" (
        echo Adding !PYTHON_DIR! to PATH...
        setx PATH "%PATH%;!PYTHON_DIR!;!PYTHON_DIR!\Scripts;" >nul
        echo PATH updated. Please CLOSE and REOPEN CMD.
        pause
        exit /b 1
    ) else (
        echo [ERROR] python.exe NOT found in "!PYTHON_DIR!".
        echo Setup aborted.
        pause
        exit /b 1
    )
)

REM ============================================================
REM 1. CREATE VENV
REM ============================================================
echo.
echo Creating virtual environment...
python -m venv venv
IF ERRORLEVEL 1 (
    echo [ERROR] Failed to create venv.
    pause
    exit /b 1
)

REM ============================================================
REM 2. ACTIVATE VENV
REM ============================================================
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
IF ERRORLEVEL 1 (
    echo [ERROR] Could not activate venv.
    pause
    exit /b 1
)

REM ============================================================
REM 3. UPGRADE PIP
REM ============================================================
echo.
echo Upgrading pip...
python -m pip install --upgrade pip
IF ERRORLEVEL 1 (
    echo [ERROR] pip upgrade failed!
    pause
    exit /b 1
)

REM ============================================================
REM 4. INSTALL REQUIREMENTS
REM ============================================================
echo.
echo Installing requirements from requirements.txt ...
echo.
pip install -r requirements.txt
IF ERRORLEVEL 1 (
    echo.
    echo *******************************************************
    echo [FATAL ERROR] FAILED TO INSTALL PYTHON PACKAGES
    echo The error message above explains the cause.
    echo *******************************************************
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SUCCESS! All packages installed.
echo ============================================================
echo.
pause
exit /b 0
