@echo off
echo Stopping any running bot...
taskkill /F /IM python.exe 2>nul

echo.
echo Starting bot with virtual environment...
call start.bat
