@echo off
title LLM PAPER TRADER
call venv\Scripts\activate.bat
echo.
echo   LLM PAPER TRADER starting...
echo   Dashboard: http://localhost:5050
echo   Stop: Ctrl+C or close this window
echo.
python main.py
pause
