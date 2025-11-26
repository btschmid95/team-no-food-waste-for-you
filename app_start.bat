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

    if defined PYTHON_DIR (
        echo Found Python installation at: %PYTHON_DIR%
        echo Adding to PATH...

        setx PATH "%PATH%;%PYTHON_DIR%;%PYTHON_DIR%\Scripts;" >nul

        echo PATH updated. Please CLOSE and REOPEN this window, then run again.
        pause
        exit /b 1
    ) else (
        echo Could not auto-detect Python.
        echo Please enter the folder containing python.exe (example: C:\Users\User\AppData\Local\Programs\Python\Python311)
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

REM 1. CREATE VENV
echo.
echo Creating virtual environment...
python -m venv venv
IF ERRORLEVEL 1 (
    echo [ERROR] Failed to create venv.
    pause
    exit /b 1
)

REM 2. ACTIVATE VENV
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
IF ERRORLEVEL 1 (
    echo [ERROR] Could not activate venv.
    pause
    exit /b 1
)

REM 3. UPGRADE PIP
echo.
echo Upgrading pip...
python -m pip install --upgrade pip
IF ERRORLEVEL 1 (
    echo [ERROR] pip upgrade failed!
    pause
    exit /b 1
)

REM 4. INSTALL REQUIREMENTS
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
