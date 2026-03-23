@echo off
echo =========================================
echo       Starting JobSee Dashboard
echo =========================================

echo [1/3] Activating uv environment...
call ..\venv\Scripts\activate.bat

echo [2/3] Installing/Verifying dependencies...
uv pip install -r backend\requirements.txt

cd backend

echo [3/3] Launching Job Tracker Background API Server...
start "JobSee API Backend" python main.py

echo Launching JobSee Streamlit Dashboard in browser...
streamlit run app.py
