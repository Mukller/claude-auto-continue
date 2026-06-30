@echo off
"C:\Users\Ecat\AppData\Local\Programs\Python\Python313\python.exe" "%~dp0claude_continue_gui.py"
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА запуска. Установите зависимости:
    echo pip install pyautogui pygetwindow pillow uiautomation
    pause
)
