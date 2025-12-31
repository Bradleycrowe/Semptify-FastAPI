<#
.SYNOPSIS
    Creates a distributable Semptify 5.0 Windows package
    
.DESCRIPTION
    Packages Semptify source code into a ZIP file for distribution
    
.PARAMETER OutputPath
    Where to save the distribution package (default: desktop)
    
.PARAMETER IncludeDemoData
    Include sample data files (default: false)
#>

param(
    [string]$OutputPath = "$env:USERPROFILE\Desktop",
    [switch]$IncludeDemoData = $false
)

$ErrorActionPreference = "Stop"

# Get script directory (assumes running from installer folder)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "     Semptify 5.0 - Distribution Package Builder              " -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

$timestamp = Get-Date -Format "yyyyMMdd"
$packageName = "Semptify5.0-Windows-$timestamp"
$zipPath = Join-Path $OutputPath "$packageName.zip"

Write-Host "[*] Building distribution package..." -ForegroundColor Yellow
Write-Host "    Source: $ProjectRoot" -ForegroundColor Gray
Write-Host "    Output: $zipPath" -ForegroundColor Gray
Write-Host ""

# Create temp directory for packaging
$tempDir = Join-Path $env:TEMP "semptify-dist-$timestamp"
$packageDir = Join-Path $tempDir $packageName

if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $packageDir -Force | Out-Null

Write-Host "[1/6] Copying application code..." -ForegroundColor Yellow

# Copy main application files
$includeFolders = @(
    "app",
    "alembic",
    "docs",
    "scripts",
    "static",
    "templates",
    "installer"
)

foreach ($folder in $includeFolders) {
    $srcPath = Join-Path $ProjectRoot $folder
    if (Test-Path $srcPath) {
        $destPath = Join-Path $packageDir $folder
        Copy-Item $srcPath $destPath -Recurse -Force
        Write-Host "    [OK] $folder" -ForegroundColor Green
    }
}

Write-Host "[2/6] Copying configuration files..." -ForegroundColor Yellow

# Copy root files
$includeFiles = @(
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "alembic.ini",
    "pytest.ini",
    "LICENSE",
    "README.md",
    "QUICKSTART.md",
    "USER_JOURNEY_GUIDE.md",
    "START.ps1",
    "START.bat",
    "Semptify.bat",
    "run_server.py"
)

foreach ($file in $includeFiles) {
    $srcPath = Join-Path $ProjectRoot $file
    if (Test-Path $srcPath) {
        Copy-Item $srcPath $packageDir -Force
        Write-Host "    [OK] $file" -ForegroundColor Green
    }
}

Write-Host "[3/6] Creating environment template..." -ForegroundColor Yellow

# Create .env.example content
$envContent = "# Semptify 5.0 Configuration`n"
$envContent += "`n"
$envContent += "# Database (PostgreSQL recommended for production)`n"
$envContent += "DATABASE_URL=postgresql+asyncpg://postgres:Semptify2024!@localhost:5432/semptify`n"
$envContent += "# For SQLite: DATABASE_URL=sqlite+aiosqlite:///./semptify.db`n"
$envContent += "`n"
$envContent += "# Server Configuration`n"
$envContent += "HOST=0.0.0.0`n"
$envContent += "PORT=8000`n"
$envContent += "DEBUG=false`n"
$envContent += "`n"
$envContent += "# Security`n"
$envContent += "SECRET_KEY=your-secret-key-change-in-production`n"
$envContent += "ACCESS_TOKEN_EXPIRE_MINUTES=30`n"

$envExamplePath = Join-Path $packageDir ".env.example"
Set-Content -Path $envExamplePath -Value $envContent -Encoding UTF8
Write-Host "    [OK] .env.example" -ForegroundColor Green

Write-Host "[4/6] Copying installer files to root..." -ForegroundColor Yellow

# Copy installer files to root for easy access
$installerFiles = @(
    "Install-Semptify.bat",
    "install_semptify.ps1",
    "WINDOWS_INSTALL_GUIDE.md",
    "DISTRIBUTION_README.md",
    "INSTALL_INSTRUCTIONS.html"
)

foreach ($file in $installerFiles) {
    $srcPath = Join-Path $ProjectRoot "installer\$file"
    if (Test-Path $srcPath) {
        Copy-Item $srcPath $packageDir -Force
        Write-Host "    [OK] $file" -ForegroundColor Green
    }
}

# Copy offline dependencies if they exist
$depsPath = Join-Path $ProjectRoot "installer\dependencies"
if (Test-Path $depsPath) {
    Write-Host "    Copying offline installers..." -ForegroundColor Gray
    Copy-Item $depsPath $packageDir -Recurse -Force
    # Move subfolders to root level for easier access
    $postgresDir = Join-Path $packageDir "dependencies\postgresql"
    $pythonDir = Join-Path $packageDir "dependencies\python"
    if (Test-Path $postgresDir) {
        Move-Item $postgresDir $packageDir -Force
        Write-Host "    [OK] postgresql/ (offline installer)" -ForegroundColor Green
    }
    if (Test-Path $pythonDir) {
        Move-Item $pythonDir $packageDir -Force
        Write-Host "    [OK] python/ (offline installer)" -ForegroundColor Green
    }
    Remove-Item (Join-Path $packageDir "dependencies") -Recurse -Force -ErrorAction SilentlyContinue
}

# Rename DISTRIBUTION_README.md to README-INSTALL.md in root
$distReadme = Join-Path $packageDir "DISTRIBUTION_README.md"
if (Test-Path $distReadme) {
    Rename-Item $distReadme "README-INSTALL.md"
}

Write-Host "[5/6] Creating required directories..." -ForegroundColor Yellow

# Create empty required directories
$emptyDirs = @(
    "data",
    "data\documents",
    "data\cases",
    "data\intake",
    "logs",
    "uploads"
)

foreach ($dir in $emptyDirs) {
    $dirPath = Join-Path $packageDir $dir
    New-Item -ItemType Directory -Path $dirPath -Force | Out-Null
    
    # Add .gitkeep
    New-Item -ItemType File -Path (Join-Path $dirPath ".gitkeep") -Force | Out-Null
}
Write-Host "    [OK] Data directories created" -ForegroundColor Green

if ($IncludeDemoData) {
    Write-Host "[5b] Copying demo data..." -ForegroundColor Yellow
    $demoDataSrc = Join-Path $ProjectRoot "data"
    if (Test-Path $demoDataSrc) {
        Copy-Item "$demoDataSrc\*" (Join-Path $packageDir "data") -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "    [OK] Demo data included" -ForegroundColor Green
    }
}

Write-Host "[6/6] Creating ZIP archive..." -ForegroundColor Yellow

# Remove any existing zip
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

# Create ZIP
Compress-Archive -Path "$packageDir\*" -DestinationPath $zipPath -CompressionLevel Optimal

# Cleanup temp
Remove-Item $tempDir -Recurse -Force

# Get file size
$zipSize = (Get-Item $zipPath).Length / 1MB

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host "              PACKAGE CREATED SUCCESSFULLY!                   " -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Package Details:" -ForegroundColor White
Write-Host "  File: $zipPath" -ForegroundColor Cyan
Write-Host "  Size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Gray
Write-Host ""
Write-Host "Distribution Instructions:" -ForegroundColor Yellow
Write-Host "  1. Transfer the ZIP file to the target Windows system" -ForegroundColor Gray
Write-Host "  2. Extract the ZIP to desired location" -ForegroundColor Gray
Write-Host "  3. Right-click Install-Semptify.bat - Run as Administrator" -ForegroundColor Gray
Write-Host "  4. Follow the installation prompts" -ForegroundColor Gray
Write-Host ""

# Open folder containing the package
explorer.exe /select,$zipPath

Write-Host "Press any key to exit..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
