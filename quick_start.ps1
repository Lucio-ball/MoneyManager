param(
    [switch]$SeedData,
    [switch]$ResetData,
    [int]$Months = 6,
    [int]$Seed = 20260226,
    [switch]$SkipInstall,
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 5000,
    [switch]$NoRun
)

$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }

    throw "Python not found. Please install Python 3.10+ and add it to PATH."
}

function Invoke-Python {
    param(
        [string[]]$PyCmd,
        [string[]]$ScriptArgs
    )

    if ($PyCmd.Length -eq 2) {
        & $PyCmd[0] $PyCmd[1] @ScriptArgs
    }
    else {
        & $PyCmd[0] @ScriptArgs
    }
}

Write-Host "== MoneyManager Quick Start ==" -ForegroundColor Cyan

$pythonCmd = Resolve-PythonCommand
Write-Host ("Python command: " + ($pythonCmd -join " ")) -ForegroundColor DarkGray

if (-not $SkipInstall) {
    Write-Host "[1/4] Installing dependencies..." -ForegroundColor Yellow
    Invoke-Python -PyCmd $pythonCmd -ScriptArgs @("-m", "pip", "install", "-r", "requirements.txt")
}
else {
    Write-Host "[1/4] Skipped dependency install (--SkipInstall)" -ForegroundColor DarkYellow
}

if ($SeedData) {
    Write-Host "[2/4] Generating seed data..." -ForegroundColor Yellow
    $seedArgs = @("seed_data.py", "--months", "$Months", "--seed", "$Seed")
    if ($ResetData) {
        $seedArgs += "--reset"
    }
    Invoke-Python -PyCmd $pythonCmd -ScriptArgs $seedArgs
}
else {
    Write-Host "[2/4] Skipped seed data generation (use -SeedData)" -ForegroundColor DarkYellow
}

Write-Host "[3/4] Checking app import..." -ForegroundColor Yellow
Invoke-Python -PyCmd $pythonCmd -ScriptArgs @("-c", "from app import app; print('App import OK')")

if ($NoRun) {
    Write-Host "[4/4] NoRun mode: service not started." -ForegroundColor Green
    exit 0
}

Write-Host "[4/4] Starting service..." -ForegroundColor Yellow
Write-Host "URL: http://$BindHost`:$Port" -ForegroundColor Green
$env:FLASK_RUN_HOST = $BindHost
$env:FLASK_RUN_PORT = "$Port"

Invoke-Python -PyCmd $pythonCmd -ScriptArgs @("app.py")
