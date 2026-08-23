@echo off
setlocal
rem Ищем Python в системе (py-launcher или python в PATH), без захардкоженных путей.
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python not found. Install it from https://www.python.org/downloads/
    pause
    exit /b 1
)
%PY% "%~dp0claude_continue_gui.py"
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА запуска. Установите зависимости:
    echo pip install -r "%~dp0requirements.txt"
    pause
)
