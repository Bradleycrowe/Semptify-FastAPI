<#
.SYNOPSIS
    Semptify 5.0 Windows Installer
    
.DESCRIPTION
    Automated installer for Semptify Tenant Rights Platform.
    Installs Python, PostgreSQL (optional), and all dependencies.
    
.PARAMETER InstallPath
    Installation directory (default: C:\Semptify)
    
.PARAMETER UsePostgreSQL
    Install and configure PostgreSQL (default: true)
    
.PARAMETER CreateShortcut
    Create desktop shortcut (default: true)
    
.PARAMETER InstallService
    Install as Windows service for auto-start (default: false)
    
.PARAMETER SkipPython
    Skip Python installation if already installed
    
.EXAMPLE
    .\install_semptify.ps1
    
.EXAMPLE
    .\install_semptify.ps1 -InstallPath "D:\Apps\Semptify" -InstallService
#>

param(
    [string]$InstallPath = "C:\Semptify\Semptify-FastAPI",
    [switch]$UsePostgreSQL = $true,
    [switch]$CreateShortcut = $true,
    [switch]$InstallService = $false,
    [switch]$SkipPython = $false,
    [string]$PostgresPassword = "Semptify2024!"
)

# Require Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️  This installer requires Administrator privileges." -ForegroundColor Yellow
    Write-Host "    Please right-click and 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

$ErrorActionPreference = "Stop"

# Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                              ║" -ForegroundColor Cyan
Write-Host "║   ███████╗███████╗███╗   ███╗██████╗ ████████╗██╗███████╗   ║" -ForegroundColor Cyan
Write-Host "║   ██╔════╝██╔════╝████╗ ████║██╔══██╗╚══██╔══╝██║██╔════╝   ║" -ForegroundColor Cyan
Write-Host "║   ███████╗█████╗  ██╔████╔██║██████╔╝   ██║   ██║█████╗     ║" -ForegroundColor Cyan
Write-Host "║   ╚════██║██╔══╝  ██║╚██╔╝██║██╔═══╝    ██║   ██║██╔══╝     ║" -ForegroundColor Cyan
Write-Host "║   ███████║███████╗██║ ╚═╝ ██║██║        ██║   ██║██║        ║" -ForegroundColor Cyan
Write-Host "║   ╚══════╝╚══════╝╚═╝     ╚═╝╚═╝        ╚═╝   ╚═╝╚═╝        ║" -ForegroundColor Cyan
Write-Host "║                                                              ║" -ForegroundColor Cyan
Write-Host "║          Tenant Rights Protection Platform v5.0             ║" -ForegroundColor Cyan
Write-Host "║                  Windows Installer                          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

function Write-Step {
    param([string]$Message, [string]$Status = "...")
    Write-Host "[$Status] " -NoNewline -ForegroundColor Yellow
    Write-Host $Message
}

function Write-Success {
    param([string]$Message)
    Write-Host "[✓] " -NoNewline -ForegroundColor Green
    Write-Host $Message
}

function Write-Error {
    param([string]$Message)
    Write-Host "[✗] " -NoNewline -ForegroundColor Red
    Write-Host $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "[i] " -NoNewline -ForegroundColor Cyan
    Write-Host $Message
}

# Check if running from source or standalone
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$IsSourceInstall = Test-Path (Join-Path $ScriptDir "..\app\main.py")

Write-Host "Installation Configuration:" -ForegroundColor White
Write-Host "  Install Path:    $InstallPath" -ForegroundColor Gray
Write-Host "  PostgreSQL:      $UsePostgreSQL" -ForegroundColor Gray
Write-Host "  Desktop Shortcut: $CreateShortcut" -ForegroundColor Gray
Write-Host "  Windows Service: $InstallService" -ForegroundColor Gray
Write-Host ""

# ============================================================================
# Step 1: Check/Install Python
# ============================================================================
Write-Step "Checking Python installation"

$pythonCmd = $null
$pythonPaths = @(
    "python",
    "python3",
    "C:\Python312\python.exe",
    "C:\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)

foreach ($path in $pythonPaths) {
    try {
        $version = & $path --version 2>$null
        if ($version -match "Python 3\.(1[1-9]|[2-9][0-9])") {
            $pythonCmd = $path
            Write-Success "Found $version at $path"
            break
        }
    } catch {}
}

if (-not $pythonCmd -and -not $SkipPython) {
    Write-Step "Installing Python 3.12"
    
    # Check for offline installer first
    $offlinePython = Join-Path $ScriptDir "python\python-3.12.0-amd64.exe"
    if (-not (Test-Path $offlinePython)) {
        $offlinePython = Join-Path $ScriptDir "..\python\python-3.12.0-amd64.exe"
    }
    
    if (Test-Path $offlinePython) {
        Write-Info "Using offline Python installer"
        Start-Process -FilePath $offlinePython -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0" -Wait
    } else {
        # Try winget
        try {
            winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        } catch {
            Write-Error "Failed to install Python: $_"
            Write-Info "Please install Python 3.11+ manually from https://python.org"
            Write-Info "Or place python-3.12.0-amd64.exe in the python/ folder"
            exit 1
        }
    }
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    # Find python again
    foreach ($path in $pythonPaths) {
        try {
            $version = & $path --version 2>$null
            if ($version -match "Python 3") {
                $pythonCmd = $path
                break
            }
        } catch {}
    }
    
    if ($pythonCmd) {
        Write-Success "Python installed successfully"
    } else {
        Write-Error "Python installation may require system restart"
        Write-Info "After restart, run this installer again with -SkipPython"
    }
}

if (-not $pythonCmd) {
    Write-Error "Python 3.11+ is required but not found"
    exit 1
}

# ============================================================================
# Step 2: Check/Install PostgreSQL (Optional)
# ============================================================================
if ($UsePostgreSQL) {
    Write-Step "Checking PostgreSQL installation"
    
    $pgService = Get-Service postgresql* -ErrorAction SilentlyContinue
    
    if ($pgService) {
        Write-Success "PostgreSQL is installed (Service: $($pgService.Name))"
        
        if ($pgService.Status -ne "Running") {
            Write-Step "Starting PostgreSQL service"
            Start-Service $pgService.Name
            Write-Success "PostgreSQL service started"
        }
    } else {
        Write-Step "Installing PostgreSQL 16"
        
        # Check for offline installer first
        $offlinePostgres = Join-Path $ScriptDir "postgresql\postgresql-16-windows-x64.exe"
        if (-not (Test-Path $offlinePostgres)) {
            $offlinePostgres = Join-Path $ScriptDir "..\postgresql\postgresql-16-windows-x64.exe"
        }
        
        if (Test-Path $offlinePostgres) {
            Write-Info "Using offline PostgreSQL installer"
            Write-Info "IMPORTANT: Set password to: $PostgresPassword"
            
            # Run PostgreSQL installer with unattended options
            $pgArgs = @(
                "--mode", "unattended",
                "--unattendedmodeui", "minimal",
                "--superpassword", $PostgresPassword,
                "--serverport", "5432",
                "--servicename", "postgresql-x64-16"
            )
            
            Start-Process -FilePath $offlinePostgres -ArgumentList $pgArgs -Wait
            
            Start-Sleep -Seconds 5
            $pgService = Get-Service postgresql* -ErrorAction SilentlyContinue
            if ($pgService) {
                Write-Success "PostgreSQL installed successfully from offline installer"
            }
        } else {
            # Try winget
            try {
                winget install PostgreSQL.PostgreSQL.16 --accept-package-agreements --accept-source-agreements
                
                Start-Sleep -Seconds 5
                
                $pgService = Get-Service postgresql* -ErrorAction SilentlyContinue
                if ($pgService) {
                    Write-Success "PostgreSQL installed successfully"
                } else {
                    Write-Info "PostgreSQL installed - may require restart to start service"
                }
            } catch {
                Write-Error "Failed to install PostgreSQL: $_"
                Write-Info "Falling back to SQLite database"
                Write-Info "Or place postgresql-16-windows-x64.exe in the postgresql/ folder"
                $UsePostgreSQL = $false
            }
        }
    }
}

# ============================================================================
# Step 3: Setup Application Directory
# ============================================================================
Write-Step "Setting up application directory"

if ($IsSourceInstall) {
    # Running from source - use parent directory
    $InstallPath = Split-Path -Parent $ScriptDir
    Write-Info "Installing from source at: $InstallPath"
} else {
    # Clone or copy repository
    if (-not (Test-Path $InstallPath)) {
        Write-Step "Downloading Semptify from GitHub"
        
        $gitAvailable = $null -ne (Get-Command git -ErrorAction SilentlyContinue)
        
        if ($gitAvailable) {
            git clone https://github.com/Bradleycrowe/Semptify5.0.git $InstallPath
        } else {
            # Download ZIP
            $zipUrl = "https://github.com/Bradleycrowe/Semptify5.0/archive/refs/heads/main.zip"
            $zipPath = "$env:TEMP\semptify.zip"
            
            Write-Step "Downloading from GitHub"
            Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
            
            Write-Step "Extracting files"
            Expand-Archive -Path $zipPath -DestinationPath "$env:TEMP\semptify-extract" -Force
            
            # Move to install path
            $extractedFolder = Get-ChildItem "$env:TEMP\semptify-extract" | Select-Object -First 1
            Move-Item $extractedFolder.FullName $InstallPath
            
            Remove-Item $zipPath -Force
            Remove-Item "$env:TEMP\semptify-extract" -Recurse -Force
        }
        
        Write-Success "Semptify downloaded to $InstallPath"
    } else {
        Write-Info "Using existing installation at $InstallPath"
    }
}

Set-Location $InstallPath

# ============================================================================
# Step 4: Create Virtual Environment
# ============================================================================
Write-Step "Creating Python virtual environment"

$venvPath = Join-Path $InstallPath ".venv"

if (-not (Test-Path $venvPath)) {
    & $pythonCmd -m venv $venvPath
    Write-Success "Virtual environment created"
} else {
    Write-Info "Virtual environment already exists"
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

# ============================================================================
# Step 5: Install Dependencies
# ============================================================================
Write-Step "Installing Python dependencies"

& $venvPip install --upgrade pip --quiet
& $venvPip install -r requirements.txt --quiet

if ($UsePostgreSQL) {
    & $venvPip install asyncpg --quiet
}

Write-Success "Dependencies installed"

# ============================================================================
# Step 6: Configure Environment
# ============================================================================
Write-Step "Configuring environment"

$envFile = Join-Path $InstallPath ".env"

if (-not (Test-Path $envFile)) {
    # Copy from example if exists
    $envExample = Join-Path $InstallPath ".env.example"
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
    }
}

# Update database URL based on choice
if ($UsePostgreSQL) {
    $dbUrl = "postgresql+asyncpg://postgres:$PostgresPassword@localhost:5432/semptify"
    
    # Create database if PostgreSQL is available
    $psqlPath = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
    if (Test-Path $psqlPath) {
        Write-Step "Creating PostgreSQL database"
        
        $env:PGPASSWORD = $PostgresPassword
        try {
            & $psqlPath -U postgres -h 127.0.0.1 -c "CREATE DATABASE semptify;" 2>$null
            Write-Success "Database 'semptify' created"
        } catch {
            Write-Info "Database may already exist"
        }
    }
} else {
    $dbUrl = "sqlite+aiosqlite:///./semptify.db"
}

# Update .env file
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    $envContent = $envContent -replace 'DATABASE_URL=.*', "DATABASE_URL=$dbUrl"
    Set-Content $envFile $envContent
    Write-Success "Environment configured"
}

# ============================================================================
# Step 7: Initialize Database
# ============================================================================
Write-Step "Initializing database tables"

try {
    & $venvPython scripts/init_postgres.py 2>$null
    Write-Success "Database initialized"
} catch {
    Write-Info "Database initialization skipped or already done"
}

# ============================================================================
# Step 8: Create Desktop Shortcut
# ============================================================================
if ($CreateShortcut) {
    Write-Step "Creating desktop shortcut"
    
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Semptify.lnk")
    $Shortcut.TargetPath = Join-Path $InstallPath "START.ps1"
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.IconLocation = Join-Path $InstallPath "static\favicon.ico"
    $Shortcut.Description = "Semptify - Tenant Rights Protection Platform"
    $Shortcut.Save()
    
    Write-Success "Desktop shortcut created"
}

# ============================================================================
# Step 9: Install as Service (Optional)
# ============================================================================
if ($InstallService) {
    Write-Step "Installing Windows service"
    
    # Check for NSSM
    $nssmPath = Get-Command nssm -ErrorAction SilentlyContinue
    
    if (-not $nssmPath) {
        Write-Step "Installing NSSM (service manager)"
        winget install nssm --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    }
    
    # Remove existing service if present
    nssm stop Semptify 2>$null
    nssm remove Semptify confirm 2>$null
    
    # Install service
    nssm install Semptify $venvPython
    nssm set Semptify AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    nssm set Semptify AppDirectory $InstallPath
    nssm set Semptify DisplayName "Semptify Tenant Rights Platform"
    nssm set Semptify Description "Tenant rights protection and document management"
    nssm set Semptify Start SERVICE_AUTO_START
    nssm set Semptify AppStdout (Join-Path $InstallPath "logs\service.log")
    nssm set Semptify AppStderr (Join-Path $InstallPath "logs\service-error.log")
    
    # Create logs directory
    New-Item -ItemType Directory -Path (Join-Path $InstallPath "logs") -Force | Out-Null
    
    # Start service
    nssm start Semptify
    
    Write-Success "Windows service installed and started"
}

# ============================================================================
# Complete!
# ============================================================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "║              ✅ INSTALLATION COMPLETE!                       ║" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "Installation Summary:" -ForegroundColor White
Write-Host "  📁 Location:     $InstallPath" -ForegroundColor Gray
Write-Host "  🐍 Python:       $pythonCmd" -ForegroundColor Gray
Write-Host "  🗄️  Database:     $(if ($UsePostgreSQL) { 'PostgreSQL' } else { 'SQLite' })" -ForegroundColor Gray
Write-Host "  🔗 URL:          http://localhost:8000" -ForegroundColor Gray
Write-Host "  📚 API Docs:     http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""

if (-not $InstallService) {
    Write-Host "To start Semptify:" -ForegroundColor Yellow
    Write-Host "  Option 1: Double-click 'Semptify' shortcut on desktop" -ForegroundColor Gray
    Write-Host "  Option 2: Run: cd $InstallPath && .\START.ps1" -ForegroundColor Gray
    Write-Host "  Option 3: Run: cd $InstallPath && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000" -ForegroundColor Gray
} else {
    Write-Host "Semptify is running as a Windows service!" -ForegroundColor Yellow
    Write-Host "  Service Name: Semptify" -ForegroundColor Gray
    Write-Host "  To stop:  Stop-Service Semptify" -ForegroundColor Gray
    Write-Host "  To start: Start-Service Semptify" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Database Credentials:" -ForegroundColor Yellow
Write-Host "  Database: semptify" -ForegroundColor Gray
Write-Host "  User:     postgres" -ForegroundColor Gray
Write-Host "  Password: $PostgresPassword" -ForegroundColor Gray
Write-Host ""

Write-Host "Press any key to exit..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
