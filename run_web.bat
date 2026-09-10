@echo off
title Background Remover Pro - Web App
echo Starting Background Remover Pro (Streamlit Web App)...
streamlit run app.py
if errorlevel 1 (
    echo.
    echo Web app exited with an error.
    pause
)
