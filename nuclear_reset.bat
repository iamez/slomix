@echo off
REM Nuclear Database Reset and Import
REM Wipes database and reimports all stats from local_stats/

echo.
echo ========================================
echo   NUCLEAR DATABASE RESET
echo ========================================
echo.
echo This will:
echo   1. Backup current database
echo   2. Delete and recreate database
echo   3. Import ALL files from local_stats/
echo   4. Show detailed logs
echo.

set /p CONFIRM="Are you SURE? Type 'YES' to continue: "
if not "%CONFIRM%"=="YES" (
    echo Cancelled.
    pause
    exit /b 1
)

echo.
echo [1/4] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [2/4] Creating backup of current database...
set BACKUP_FILE=bot\etlegacy_production_backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.db
set BACKUP_FILE=%BACKUP_FILE: =0%
copy bot\etlegacy_production.db "%BACKUP_FILE%"
echo Backup saved: %BACKUP_FILE%

echo.
echo [3/4] Running postgresql_database_manager.py...
echo     Select option 2 (Rebuild from scratch)
echo     When prompted for year filter, press ENTER for all years
echo.
pause

python postgresql_database_manager.py

echo.
echo [4/4] Import complete! Checking results...
python -c "import sqlite3; conn = sqlite3.connect('bot/etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); total = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(DISTINCT round_date) FROM player_comprehensive_stats'); dates = cursor.fetchone()[0]; cursor.execute('SELECT MIN(round_date), MAX(round_date) FROM player_comprehensive_stats'); date_range = cursor.fetchone(); print(f'\n=== IMPORT SUMMARY ==='); print(f'Total records: {total:,}'); print(f'Unique dates: {dates}'); print(f'Date range: {date_range[0]} to {date_range[1]}'); print('=====================\n')"

echo.
echo ========================================
echo   Nuclear reset complete!
echo ========================================
pause
