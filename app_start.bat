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
echo Checking Python installation...
python --version >nul 2>&1

IF NOT ERRORLEVEL 1 (
    echo Python detected.
) ELSE (
    echo Python not found in PATH. Attempting auto-detection...

    REM Attempt to locate Python under LocalAppData common install
    set "PYTHON_DIR="
    for /d %%D in ("%LocalAppData%\Programs\Python\Python*") do (
        set "PYTHON_DIR=%%D"
    )

    REM VALIDATE auto-detected folder
    if defined PYTHON_DIR if exist "%PYTHON_DIR%\python.exe" (
        echo Found Python installation at: %PYTHON_DIR%
        echo Adding to PATH...

        setx PATH "%PATH%;%PYTHON_DIR%;%PYTHON_DIR%\Scripts;" >nul

        echo PATH updated. Please CLOSE and REOPEN this window, then run again.
        pause
        exit /b 1
    ) else (
        echo Auto-detection failed — Python folder invalid or not found.
        echo.
        echo Please enter the folder containing python.exe
        echo Example:
        echo   C:\Users\User\AppData\Local\Programs\Python\Python311
        echo.

        set /p PYTHON_DIR="Python install path: "

        if exist "%PYTHON_DIR%\python.exe" (
            echo Adding %PYTHON_DIR% to PATH...
            setx PATH "%PATH%;%PYTHON_DIR%;%PYTHON_DIR%\Scripts;" >nul

            echo PATH updated. Please CLOSE and REOPEN this window, then run again.
            pause
            exit /b 1
        ) else (
            echo [ERROR] No python.exe found in that folder.
            echo Setup aborted.
            pause
            exit /b 1
        )
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
