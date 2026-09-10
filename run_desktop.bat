@echo off
title Background Remover Pro - Desktop
echo Starting Background Remover Pro (Desktop GUI)...
python main.py
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
