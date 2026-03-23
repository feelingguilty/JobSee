@echo off
echo =========================================
echo       Stopping JobSee Dashboard
echo =========================================

echo Terminating Streamlit and Uvicorn/Python processes...
taskkill /IM "python.exe" /F /T
echo Done.
pause
