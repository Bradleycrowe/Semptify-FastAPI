# Semptify 5.0 - Windows Installation Guide

## 🚀 Quick Install (Automated)

**Run as Administrator:**

```powershell
# Download and run the installer
powershell -ExecutionPolicy Bypass -File install_semptify.ps1
```

Or double-click `Install-Semptify.bat`

---

## 📋 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 | Windows 11 |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 2 GB free | 5 GB free |
| **Python** | 3.11+ | 3.12+ |
| **Database** | SQLite (included) | PostgreSQL 16 |

---

## 📦 What Gets Installed

1. **Python 3.12** (if not present)
2. **PostgreSQL 16** (optional, for production)
3. **Semptify Application** + all dependencies
4. **Desktop Shortcut** (optional)
5. **Windows Service** (optional, for auto-start)

---

## 🔧 Manual Installation

### Step 1: Install Python

```powershell
# Using winget (Windows Package Manager)
winget install Python.Python.3.12

# Verify installation
python --version
```

### Step 2: Install PostgreSQL (Optional but Recommended)

```powershell
# Using winget
winget install PostgreSQL.PostgreSQL.16

# During install, set password: Semptify2024!
```

### Step 3: Download Semptify

```powershell
# Clone repository
git clone https://github.com/Bradleycrowe/Semptify5.0.git C:\Semptify

# Or download ZIP from GitHub and extract to C:\Semptify
```

### Step 4: Setup Virtual Environment

```powershell
cd C:\Semptify\Semptify-FastAPI

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Configure Database

**Option A: SQLite (Simple, No Setup)**
```powershell
# Edit .env file - already configured by default
# DATABASE_URL=sqlite+aiosqlite:///./semptify.db
```

**Option B: PostgreSQL (Production)**
```powershell
# 1. Create database
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE semptify;"

# 2. Edit .env file
notepad .env
# Set: DATABASE_URL=postgresql+asyncpg://postgres:Semptify2024!@localhost:5432/semptify

# 3. Initialize tables
python scripts/init_postgres.py
```

### Step 6: Run Semptify

```powershell
# Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or use the start script
.\START.ps1
```

### Step 7: Access Semptify

Open browser: **http://localhost:8000**

---

## 🖥️ Create Desktop Shortcut

```powershell
# Run from project folder
powershell -ExecutionPolicy Bypass -File CreateDesktopShortcut.ps1
```

---

## ⚙️ Install as Windows Service (Auto-Start)

```powershell
# Install NSSM (Non-Sucking Service Manager)
winget install nssm

# Create service
nssm install Semptify "C:\Semptify\Semptify-FastAPI\.venv\Scripts\python.exe"
nssm set Semptify AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
nssm set Semptify AppDirectory "C:\Semptify\Semptify-FastAPI"
nssm set Semptify DisplayName "Semptify Tenant Rights Platform"
nssm set Semptify Description "Tenant rights protection and document management"
nssm set Semptify Start SERVICE_AUTO_START

# Start service
nssm start Semptify
```

---

## 🔐 Default Configuration

| Setting | Value |
|---------|-------|
| **URL** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |
| **Database** | PostgreSQL or SQLite |
| **DB Password** | Semptify2024! |
| **Upload Folder** | uploads/ |
| **Vault Folder** | uploads/vault/ |

---

## 🔧 Environment Variables (.env)

Key settings in `.env` file:

```ini
# Application
APP_NAME=Semptify
DEBUG=false

# Security
SECURITY_MODE=enforced
SECRET_KEY=your-secret-key-here

# Database (choose one)
DATABASE_URL=postgresql+asyncpg://postgres:Semptify2024!@localhost:5432/semptify
# DATABASE_URL=sqlite+aiosqlite:///./semptify.db

# AI Provider (optional)
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key-here
```

---

## 🆘 Troubleshooting

### Port 8000 Already in Use
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill it (replace PID)
taskkill /F /PID <PID>
```

### PostgreSQL Won't Connect
```powershell
# Check service is running
Get-Service postgresql*

# Start if stopped
Start-Service postgresql-x64-16
```

### Python Not Found
```powershell
# Add to PATH manually
$env:Path += ";C:\Python312;C:\Python312\Scripts"
```

### Permission Denied
```powershell
# Run PowerShell as Administrator
# Right-click PowerShell → Run as Administrator
```

---

## 📞 Support

- **GitHub Issues**: https://github.com/Bradleycrowe/Semptify5.0/issues
- **Documentation**: See `docs/` folder

---

## 📝 License

Semptify 5.0 - Tenant Rights Protection Platform
