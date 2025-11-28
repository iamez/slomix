@echo off
REM Automated Linux Deployment Script
REM Deploys ET:Legacy Discord Bot to remote Linux VPS

echo.
echo ====================================================================
echo   ET:Legacy Discord Bot - Linux Deployment
echo ====================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Please install Python 3.8+
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please create .env file with your configuration.
    pause
    exit /b 1
)

REM Install required Python packages
echo Installing required Python packages...
python -m pip install --quiet python-dotenv

REM Run deployment script
echo.
echo Starting deployment...
echo.
python deploy_to_linux.py

pause
