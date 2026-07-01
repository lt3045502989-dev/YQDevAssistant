@echo off
echo ========================================
echo  YQ Dev Assistant - Dev Environment Setup
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)
echo [OK] Python found

REM Create venv if needed
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)
echo [OK] Virtual environment ready

REM Activate and install
call .venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt
pip install -r requirements-dev.txt
echo.

REM Install in dev mode
pip install -e .
echo.

echo ========================================
echo  Setup complete!
echo  Activate venv: .venv\Scripts\activate
echo  Run CLI: yqa --help
echo ========================================
pause
