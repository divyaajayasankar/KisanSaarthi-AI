<#
.SYNOPSIS
  Start KisanSaarthi AI (chat app + API) with one command.

.EXAMPLE
  .\run_project.ps1
  .\run_project.ps1 -Port 8010
  .\run_project.ps1 -WithVision      # also installs torch/torchvision
  .\run_project.ps1 -SkipInstall     # reuse the existing .venv as it is

Works in Windows PowerShell 5.1 and PowerShell 7. If scripts are blocked:
  powershell -ExecutionPolicy Bypass -File .\run_project.ps1
#>
param(
    [int]$Port = 8000,
    [switch]$SkipInstall,
    [switch]$WithVision,
    [switch]$OpenBrowser,
    [string[]]$PipArgs = @()
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }

function Find-Python {
    foreach ($name in @("python", "python3", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -eq $cmd) { continue }
        $pyArgs = @()
        if ($name -eq "py") { $pyArgs = @("-3") }
        try {
            $ok = & $cmd.Source @pyArgs -c "import sys; print(int(sys.version_info[:2] >= (3, 10)))" 2>$null
            if ("$ok".Trim() -eq "1") { return @{ Path = $cmd.Source; Args = $pyArgs } }
        } catch { }
    }
    return $null
}

function Get-VenvPython($venvDir) {
    $win = Join-Path $venvDir "Scripts\python.exe"
    if (Test-Path $win) { return $win }
    $nix = Join-Path $venvDir "bin/python"
    if (Test-Path $nix) { return $nix }
    return $null
}

function Test-PortInUse([int]$p) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $p)
        $client.Close()
        return $true
    } catch { return $false }
}

# 1. Python ------------------------------------------------------------
Write-Step "1/6 Checking Python (3.10 or newer)"
$py = Find-Python
if ($null -eq $py) {
    Write-Host "Python 3.10+ was not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this script again." -ForegroundColor Red
    exit 1
}
Write-Host "Using $($py.Path)"

# 2. Virtual environment ----------------------------------------------
Write-Step "2/6 Virtual environment (.venv)"
$VenvDir = Join-Path $Root ".venv"
$VenvPy = Get-VenvPython $VenvDir
if ($null -eq $VenvPy) {
    Write-Host "Creating .venv ..."
    & $py.Path @($py.Args) -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Host "Could not create the virtual environment." -ForegroundColor Red; exit 1 }
    $VenvPy = Get-VenvPython $VenvDir
} else {
    Write-Host "Reusing .venv"
}

# 3. Dependencies -------------------------------------------------------
Write-Step "3/6 Dependencies"
$reqFiles = @("requirements.txt")
if ($WithVision) { $reqFiles += "requirements-vision.txt" }
$stamp = Join-Path $VenvDir ".requirements.sha256"
$hash = ($reqFiles | ForEach-Object { (Get-FileHash -Algorithm SHA256 (Join-Path $Root $_)).Hash }) -join "-"
$installed = ""
if (Test-Path $stamp) { $installed = (Get-Content $stamp -Raw).Trim() }

if ($SkipInstall) {
    Write-Host "Skipping install (-SkipInstall)"
} elseif ($installed -eq $hash) {
    Write-Host "Dependencies already installed"
} else {
    foreach ($req in $reqFiles) {
        Write-Host "Installing $req (first run takes a few minutes) ..."
        & $VenvPy -m pip install --disable-pip-version-check @PipArgs -r (Join-Path $Root $req)
        if ($LASTEXITCODE -ne 0) {
            Write-Host "pip install failed for $req. On a company network try: .\run_project.ps1 -PipArgs '--trusted-host','pypi.org','--trusted-host','files.pythonhosted.org'" -ForegroundColor Red
            exit 1
        }
    }
    Set-Content -Path $stamp -Value $hash
}

# 4. Configuration ------------------------------------------------------
Write-Step "4/6 Configuration (.env)"
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created .env from .env.example. Add your OPENWEATHER_API_KEY there."
} else {
    Write-Host ".env found"
}

# 5. Folders and checks -------------------------------------------------
Write-Step "5/6 Folders and installation check"
foreach ($dir in @("data\uploads", "data\models", "data\real_field_eval", "reports")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $dir) | Out-Null
}
& $VenvPy -m scripts.check_install
if ($LASTEXITCODE -ne 0) { Write-Host "check_install reported a problem (see above)." -ForegroundColor Yellow }

# 6. Start --------------------------------------------------------------
Write-Step "6/6 Starting the application"
if (Test-PortInUse $Port) {
    Write-Host "Port $Port is already in use. Close the other program or run: .\run_project.ps1 -Port 8010" -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "  Chat app:   http://127.0.0.1:$Port/"
Write-Host "  Classic UI: http://127.0.0.1:$Port/classic"
Write-Host "  API docs:   http://127.0.0.1:$Port/docs"
Write-Host "  Status:     http://127.0.0.1:$Port/api/status"
Write-Host ""
Write-Host "Press CTRL + C to stop." -ForegroundColor Green

if ($OpenBrowser) {
    Start-Job -ScriptBlock { param($p) Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:$p/" } -ArgumentList $Port | Out-Null
}

& $VenvPy -m uvicorn app.main:app --host 127.0.0.1 --port $Port
