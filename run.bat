@echo off
rem Запуск через python из PATH — захардкоженный локальный путь ломает
rem скрипт у всех, кроме владельца машины, и раскрывает имя пользователя.
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found in PATH. Install Python 3.9+ from python.org
    pause
    exit /b 1
)
python "%~dp0claude_continue_gui.py"
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА запуска. Установите зависимости:
    echo pip install pyautogui pillow uiautomation
    pause
)
