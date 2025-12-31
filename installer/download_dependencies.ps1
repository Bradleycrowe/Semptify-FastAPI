<#
.SYNOPSIS
    Downloads PostgreSQL and Python installers for offline distribution
    
.DESCRIPTION
    Downloads the required installers to bundle with Semptify for fully offline installation
#>

param(
    [string]$OutputPath = ".\dependencies"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Semptify 5.0 - Download Dependencies for Offline Install    " -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

# Create output directories
$postgresDir = Join-Path $OutputPath "postgresql"
$pythonDir = Join-Path $OutputPath "python"

New-Item -ItemType Directory -Path $postgresDir -Force | Out-Null
New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null

# URLs for installers
$downloads = @(
    @{
        Name = "PostgreSQL 16.1"
        URL = "https://get.enterprisedb.com/postgresql/postgresql-16.1-1-windows-x64.exe"
        Output = Join-Path $postgresDir "postgresql-16-windows-x64.exe"
    },
    @{
        Name = "Python 3.12.0"
        URL = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
        Output = Join-Path $pythonDir "python-3.12.0-amd64.exe"
    }
)

foreach ($download in $downloads) {
    Write-Host "[*] Downloading $($download.Name)..." -ForegroundColor Yellow
    Write-Host "    URL: $($download.URL)" -ForegroundColor Gray
    Write-Host "    To:  $($download.Output)" -ForegroundColor Gray
    
    if (Test-Path $download.Output) {
        Write-Host "    [SKIP] Already exists" -ForegroundColor Cyan
        continue
    }
    
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $download.URL -OutFile $download.Output -UseBasicParsing
        $ProgressPreference = 'Continue'
        
        $size = [math]::Round((Get-Item $download.Output).Length / 1MB, 2)
        Write-Host "    [OK] Downloaded ($size MB)" -ForegroundColor Green
    } catch {
        Write-Host "    [ERROR] Failed to download: $_" -ForegroundColor Red
    }
}

# Create README for dependencies
$readmeContent = @"
# Offline Installers

This folder contains installers for offline installation of Semptify dependencies.

## PostgreSQL 16
- File: postgresql/postgresql-16-windows-x64.exe
- Run this installer first
- Set password to: Semptify2024!
- Keep default port: 5432

## Python 3.12
- File: python/python-3.12.0-amd64.exe
- IMPORTANT: Check "Add Python to PATH" during installation
- Select "Install for all users" recommended

## After Installation
1. Open Command Prompt as Administrator
2. Create the database:
   cd "C:\Program Files\PostgreSQL\16\bin"
   psql -U postgres -c "CREATE DATABASE semptify;"

3. Run Semptify installer:
   Install-Semptify.bat
"@

Set-Content -Path (Join-Path $OutputPath "README.txt") -Value $readmeContent

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host "                    Downloads Complete!                        " -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Files saved to: $OutputPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Include these folders in your distribution package:" -ForegroundColor Yellow
Write-Host "  - $postgresDir" -ForegroundColor Gray
Write-Host "  - $pythonDir" -ForegroundColor Gray
