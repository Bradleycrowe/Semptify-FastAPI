# Semptify Court Defense Launcher
# One-click startup with browser selection
# Smart routing: Setup Wizard (first run) or Command Center (configured)

param(
    [string]$Browser = "",
    [string]$Profile = ""
)

$ProjectPath = "C:\Semptify\Semptify-FastAPI"
$VenvPython = "$ProjectPath\.venv\Scripts\python.exe"
$Port = 8000
$BaseUrl = "http://localhost:$Port"

# Function to check setup status and determine URL
function Get-StartupUrl {
    param($BaseUrl)
    
    try {
        # Use public /check endpoint (no auth required)
        $checkResponse = Invoke-RestMethod -Uri "$BaseUrl/api/setup/check" -TimeoutSec 3 -ErrorAction Stop
        return "$BaseUrl$($checkResponse.redirect)"
    } catch {
        # If check fails, default to setup wizard
        return "$BaseUrl/static/setup_wizard.html"
    }
}

$Url = ""  # Will be set after server starts

# Change to project directory
Set-Location $ProjectPath

# Function to show browser selection GUI
function Show-BrowserSelector {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Semptify - Court Defense System"
    $form.Size = New-Object System.Drawing.Size(400, 350)
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.BackColor = [System.Drawing.Color]::FromArgb(30, 58, 95)

    # Title
    $title = New-Object System.Windows.Forms.Label
    $title.Text = "🏠 Semptify Court Defense"
    $title.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
    $title.ForeColor = [System.Drawing.Color]::White
    $title.AutoSize = $true
    $title.Location = New-Object System.Drawing.Point(80, 20)
    $form.Controls.Add($title)

    # Browser selection
    $browserLabel = New-Object System.Windows.Forms.Label
    $browserLabel.Text = "Select Browser:"
    $browserLabel.ForeColor = [System.Drawing.Color]::LightGray
    $browserLabel.Location = New-Object System.Drawing.Point(30, 70)
    $browserLabel.AutoSize = $true
    $form.Controls.Add($browserLabel)

    $browserCombo = New-Object System.Windows.Forms.ComboBox
    $browserCombo.Location = New-Object System.Drawing.Point(30, 95)
    $browserCombo.Size = New-Object System.Drawing.Size(320, 30)
    $browserCombo.DropDownStyle = "DropDownList"
    $browserCombo.Items.Add("Microsoft Edge")
    $browserCombo.Items.Add("Google Chrome")
    $browserCombo.SelectedIndex = 0
    $form.Controls.Add($browserCombo)

    # Profile selection
    $profileLabel = New-Object System.Windows.Forms.Label
    $profileLabel.Text = "Select Profile:"
    $profileLabel.ForeColor = [System.Drawing.Color]::LightGray
    $profileLabel.Location = New-Object System.Drawing.Point(30, 140)
    $profileLabel.AutoSize = $true
    $form.Controls.Add($profileLabel)

    $profileCombo = New-Object System.Windows.Forms.ComboBox
    $profileCombo.Location = New-Object System.Drawing.Point(30, 165)
    $profileCombo.Size = New-Object System.Drawing.Size(320, 30)
    $profileCombo.DropDownStyle = "DropDownList"
    $form.Controls.Add($profileCombo)

    # Function to update profiles based on browser
    $updateProfiles = {
        $profileCombo.Items.Clear()
        if ($browserCombo.SelectedItem -eq "Microsoft Edge") {
            $profilePath = "$env:LOCALAPPDATA\Microsoft\Edge\User Data"
        } else {
            $profilePath = "$env:LOCALAPPDATA\Google\Chrome\User Data"
        }
        
        if (Test-Path $profilePath) {
            Get-ChildItem $profilePath -Directory | Where-Object { $_.Name -match "^(Default|Profile)" } | ForEach-Object {
                $profileCombo.Items.Add($_.Name)
            }
        }
        if ($profileCombo.Items.Count -gt 0) {
            $profileCombo.SelectedIndex = 0
        }
    }

    $browserCombo.add_SelectedIndexChanged($updateProfiles)
    & $updateProfiles  # Initial population

    # Launch button
    $launchBtn = New-Object System.Windows.Forms.Button
    $launchBtn.Text = "🚀 Launch Semptify"
    $launchBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
    $launchBtn.Location = New-Object System.Drawing.Point(30, 220)
    $launchBtn.Size = New-Object System.Drawing.Size(320, 50)
    $launchBtn.BackColor = [System.Drawing.Color]::FromArgb(59, 130, 246)
    $launchBtn.ForeColor = [System.Drawing.Color]::White
    $launchBtn.FlatStyle = "Flat"
    $launchBtn.add_Click({
        $form.Tag = @{
            Browser = $browserCombo.SelectedItem
            Profile = $profileCombo.SelectedItem
        }
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    })
    $form.Controls.Add($launchBtn)

    # Status label
    $statusLabel = New-Object System.Windows.Forms.Label
    $statusLabel.Text = "Ready to defend your rights in court"
    $statusLabel.ForeColor = [System.Drawing.Color]::LightGray
    $statusLabel.Location = New-Object System.Drawing.Point(30, 285)
    $statusLabel.AutoSize = $true
    $form.Controls.Add($statusLabel)

    $result = $form.ShowDialog()
    
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
        return $form.Tag
    }
    return $null
}

# Kill any existing server on port
Write-Host "🔄 Checking for existing server..." -ForegroundColor Cyan
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

# Show browser selector if not provided via params
if (-not $Browser) {
    $selection = Show-BrowserSelector
    if (-not $selection) {
        Write-Host "❌ Cancelled" -ForegroundColor Red
        exit
    }
    $Browser = $selection.Browser
    $Profile = $selection.Profile
}

Write-Host "🚀 Starting Semptify Server..." -ForegroundColor Green

# Start the server as background process
$serverProcess = Start-Process -FilePath $VenvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$Port" -WindowStyle Hidden -PassThru

# Wait for server to start
Write-Host "⏳ Waiting for server to be ready..." -ForegroundColor Yellow
$maxWait = 15
$waited = 0
while ($waited -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port/health" -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Server is ready!" -ForegroundColor Green
            break
        }
    } catch {
        Start-Sleep -Seconds 1
        $waited++
        Write-Host "." -NoNewline
    }
}

if ($waited -ge $maxWait) {
    Write-Host ""
    Write-Host "⚠️ Server may not have started properly, opening browser anyway..." -ForegroundColor Yellow
}

# Determine which page to open based on setup status
Write-Host "🔍 Checking setup status..." -ForegroundColor Cyan
$Url = Get-StartupUrl -BaseUrl $BaseUrl

if ($Url -like "*setup_wizard*") {
    Write-Host "📋 First run detected - Opening Setup Wizard" -ForegroundColor Magenta
} else {
    Write-Host "🏠 System configured - Opening Command Center" -ForegroundColor Green
}

# Launch browser with selected profile
Write-Host "🌐 Opening $Browser ($Profile)..." -ForegroundColor Cyan

if ($Browser -eq "Microsoft Edge") {
    $browserPath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if (-not (Test-Path $browserPath)) {
        $browserPath = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    }
    Start-Process $browserPath -ArgumentList "--profile-directory=`"$Profile`"", $Url
} else {
    $browserPath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (-not (Test-Path $browserPath)) {
        $browserPath = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    }
    Start-Process $browserPath -ArgumentList "--profile-directory=`"$Profile`"", $Url
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Blue
Write-Host "  SEMPTIFY COURT DEFENSE SYSTEM - RUNNING" -ForegroundColor White
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Blue
Write-Host "  URL: $Url" -ForegroundColor Cyan
Write-Host "  Server PID: $($serverProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C or close this window to stop server" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Blue

# Keep script running to maintain server
try {
    while ($true) {
        if ($serverProcess.HasExited) {
            Write-Host "⚠️ Server stopped unexpectedly" -ForegroundColor Red
            break
        }
        Start-Sleep -Seconds 5
    }
} finally {
    # Cleanup on exit
    if (-not $serverProcess.HasExited) {
        Write-Host "🛑 Stopping server..." -ForegroundColor Yellow
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
