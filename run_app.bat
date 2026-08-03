@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment was not found: .venv
    echo Create it and install requirements before running the app.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m app.main %*
if errorlevel 1 (
    echo.
    echo [ERROR] Pixel Effect Maker exited with an error.
    pause
    exit /b 1
)

endlocal
