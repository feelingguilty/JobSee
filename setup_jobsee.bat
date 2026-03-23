@echo off
echo =========================================
echo       JobSee Setup Utility
echo =========================================

echo Checking for uv...
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'uv' is not installed. Please install it first.
    pause
    exit /b 1
)

echo Creating virtual environment...
uv venv venv

echo Activating environment and installing dependencies...
call venv\Scripts\activate.bat
cd backend
uv pip install -r requirements.txt

echo.
echo =========================================
echo SUCCESS! You can now run 'start_jobsee.bat'
echo =========================================
pause
