@echo off
title Semptify 5.0 Installer
echo.
echo ============================================================
echo    SEMPTIFY 5.0 - Tenant Rights Protection Platform
echo    Windows Installer
echo ============================================================
echo.
echo This installer requires Administrator privileges.
echo.

:: Check for admin
NET SESSION >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Requesting Administrator privileges...
    echo.
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

:: Run PowerShell installer
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "install_semptify.ps1"

pause
