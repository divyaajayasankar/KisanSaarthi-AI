<#
.SYNOPSIS
  Copy YOUR data from the original project (C:\farmer) into this project.

.DESCRIPTION
  This ZIP contains the code. Your registry CSVs, database, evaluation
  images and original classic UI live in C:\farmer and are copied here.

  Copied:   frontend\index.html, app.js, style.css (classic UI -> /classic)
            data\*  (registry CSVs, coverage, rule CSVs, real_field_eval images + metadata.csv, knowledge base)
            kisansaarthi.db   (your existing database; the current one is saved as .bak first)
            .env              (only if this project has none yet)
  Never copied / never overwritten:
            data\source_datasets (multi-GB raw data), data\uploads,
            data\models, data\i18n, data\vision,
            data\registry\pest_aliases.csv (maintained in this project),
            *.pt, database backups, old frontend backups

.EXAMPLE
  .\scripts\import_local_assets.ps1 -Source C:\farmer
  .\scripts\import_local_assets.ps1 -Source C:\farmer -DryRun
#>
param(
    [string]$Source = "C:\farmer",
    [string]$Destination = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
if ($Destination -eq "") { $Destination = Split-Path -Parent $PSScriptRoot }
$Source = (Resolve-Path $Source).Path
$Destination = (Resolve-Path $Destination).Path

if (-not (Test-Path (Join-Path $Source "app\main.py"))) {
    Write-Host "Not a project folder (no app\main.py): $Source" -ForegroundColor Red
    exit 1
}
if ($Source -eq $Destination) {
    Write-Host "Source and destination are the same folder." -ForegroundColor Red
    exit 1
}

function Write-Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
Write-Host "Source:      $Source"
Write-Host "Destination: $Destination"
if ($DryRun) { Write-Host "DRY RUN: nothing is copied or changed." -ForegroundColor Yellow }

# 1. Classic UI ---------------------------------------------------------
Write-Step "Classic UI"
$srcFront = Join-Path $Source "frontend"
$dstFront = Join-Path $Destination "frontend"
if (Test-Path $srcFront) {
    New-Item -ItemType Directory -Force -Path $dstFront | Out-Null
    Get-ChildItem $srcFront -File | Where-Object {
        $_.Name -notmatch "backup|before|\.bak$|\.old$"
    } | ForEach-Object {
        Write-Host "  frontend\$($_.Name)"
        if (-not $DryRun) { Copy-Item $_.FullName (Join-Path $dstFront $_.Name) -Force }
    }
} else {
    Write-Host "  no frontend folder in source (skipped)"
}

# 2. Data -----------------------------------------------------------------
Write-Step "Data (registry, rules, evaluation images, knowledge base)"
$srcData = Join-Path $Source "data"
$dstData = Join-Path $Destination "data"
if (Test-Path $srcData) {
    New-Item -ItemType Directory -Force -Path $dstData | Out-Null
    $flags = @("/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NP")
    if ($DryRun) { $flags += "/L" }
    $xd = @("source_datasets", "uploads", "models", "i18n", "vision", "__pycache__")
    $xf = @("pest_aliases.csv", "*.pt", "*.bak", "kisansaarthi_*.db", "Thumbs.db")
    & robocopy $srcData $dstData @flags /XD @xd /XF @xf | Out-Host
    if ($LASTEXITCODE -ge 8) { Write-Host "robocopy failed (exit $LASTEXITCODE)." -ForegroundColor Red; exit 1 }
    $global:LASTEXITCODE = 0
} else {
    Write-Host "  no data folder in source (skipped)" -ForegroundColor Yellow
}

# 3. Database -------------------------------------------------------------
Write-Step "Database"
$srcDb = Join-Path $Source "kisansaarthi.db"
$dstDb = Join-Path $Destination "kisansaarthi.db"
if (Test-Path $srcDb) {
    if ((Test-Path $dstDb) -and -not $DryRun) {
        $backup = "$dstDb.bak"
        Copy-Item $dstDb $backup -Force
        Write-Host "  existing database saved as kisansaarthi.db.bak"
    }
    Write-Host "  kisansaarthi.db"
    if (-not $DryRun) { Copy-Item $srcDb $dstDb -Force }
} else {
    Write-Host "  no kisansaarthi.db in source: run your ingest scripts after this (see README)" -ForegroundColor Yellow
}

# 4. .env -------------------------------------------------------------
Write-Step "Settings (.env)"
$srcEnv = Join-Path $Source ".env"
$dstEnv = Join-Path $Destination ".env"
if ((Test-Path $srcEnv) -and -not (Test-Path $dstEnv)) {
    Write-Host "  .env will be copied (stays on this machine; the packager never includes it)"
    if (-not $DryRun) { Copy-Item $srcEnv $dstEnv }
} else {
    Write-Host "  .env left as it is"
}

if ($DryRun) { Write-Host ""; Write-Host "Dry run finished." -ForegroundColor Yellow; exit 0 }

# 5. Rebuild derived files and check ------------------------------------
Write-Step "Snapshot database for tests, audit evaluation set, validate aliases"
$py = Join-Path $Destination ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = Join-Path $Destination ".venv/bin/python" }
if (-not (Test-Path $py)) { $py = "python" }
Push-Location $Destination
try {
    if (Test-Path $dstDb) { & $py -m scripts.freeze_test_db }
    & $py -m scripts.build_eval_metadata
    & $py -m scripts.validate_pest_aliases
    & $py -m scripts.check_install
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\python.exe -m pytest -q          (data-dependent tests now run instead of skipping)"
Write-Host "  .\run_project.ps1                                 (start the app)"
Write-Host "  .\.venv\Scripts\python.exe -m scripts.package_project   (build the complete ZIP)"
