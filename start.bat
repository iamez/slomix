@echo off
echo Starting ETLegacy Discord Bot...
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install requirements
echo Installing/updating requirements...
pip install -r requirements.txt

REM Check if .env exists
if not exist ".env" (
    echo.
    echo ⚠️  WARNING: .env file not found!
    echo Please copy .env.example to .env and configure your settings.
    echo.
    pause
    exit /b 1
)

REM Start the bot
echo.
echo Starting bot...
python bot\ultimate_bot.py

pause
