@echo off
setlocal EnableDelayedExpansion

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
