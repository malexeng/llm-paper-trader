@echo off
title LLM PAPER TRADER Installer
color 0B
echo.
echo   ============================================
echo    LLM PAPER TRADER - AI CRYPTO AGENT
echo    Windows Installer
echo   ============================================
echo.
echo [1/4] Checking Python...
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo   Python not found! Install from python.org
    pause & exit /b 1
)
FOR /F "tokens=2" %%i IN ('python --version') DO echo   OK: Python %%i

echo [2/4] Creating venv...
python -m venv venv
call venv\Scripts\activate.bat

echo [3/4] Installing packages...
python -m pip install --upgrade pip -q
python -m pip install flask pyyaml ccxt requests -q
IF ERRORLEVEL 1 ( echo ERROR installing & pause & exit /b 1 )

echo [4/4] Creating dirs...
if not exist logs mkdir logs
if not exist data  mkdir data

echo.
echo   ============================================
echo    INSTALL COMPLETE
echo.
echo    BEFORE STARTING:
echo    Install Ollama from https://ollama.ai
echo    Then run: ollama pull qwen2.5:14b
echo.
echo    TO START:
echo    Double-click start.bat
echo    Open http://localhost:5050
echo    Click START
echo   ============================================
echo.
pause
