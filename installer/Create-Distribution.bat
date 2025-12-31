@echo off
title Semptify 5.0 - Create Distribution Package
echo.
echo ============================================================
echo    Creating Semptify 5.0 Distribution Package
echo ============================================================
echo.

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "create_distribution.ps1"
