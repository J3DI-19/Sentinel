[CmdletBinding()]
param(
    [ValidateRange(5, 300)]
    [int]$TimeoutSeconds = 60,

    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot "backend"
$frontendDirectory = Join-Path $repositoryRoot "frontend"
$pythonExecutable = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$environmentExample = Join-Path $repositoryRoot ".env.example"
$backendEnvironment = Join-Path $backendDirectory ".env"
$nodeModulesDirectory = Join-Path $frontendDirectory "node_modules"
$applicationUrl = "http://127.0.0.1:5173"
$apiHealthUrl = "http://127.0.0.1:8000/api/v1/health"
$databaseHealthUrl = "http://127.0.0.1:8000/api/v1/health/db"
$aiHealthUrl = "http://127.0.0.1:8000/api/v1/health/ai"

function Write-Step {
    param([string]$Message)
    Write-Host "  > $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-WarningMessage {
    param([string]$Message)
    Write-Host "  [OPTIONAL] $Message" -ForegroundColor Yellow
}

function Stop-WithError {
    param([string]$Message)
    Write-Host "  [ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Test-PortListening {
    param([int]$Port)

    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-JsonResponse {
    param([string]$Url)

    try {
        return Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2
    }
    catch {
        return $null
    }
}

function Test-Frontend {
    try {
        $response = Invoke-WebRequest -Uri $applicationUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Wait-Until {
    param(
        [scriptblock]$Condition,
        [string]$Description
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (& $Condition) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    Write-Host "  [TIMEOUT] $Description did not become ready within $TimeoutSeconds seconds." -ForegroundColor Red
    return $false
}

Write-Host "Checking local prerequisites..." -ForegroundColor White

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    Stop-WithError "Backend virtual environment is missing. Follow the Backend installation steps in README.md."
}

if (-not (Get-Command "npm.cmd" -ErrorAction SilentlyContinue)) {
    Stop-WithError "npm is not available on PATH. Install Node.js 20 or newer."
}

if (-not (Test-Path -LiteralPath $nodeModulesDirectory -PathType Container)) {
    Stop-WithError "Frontend dependencies are missing. Run 'npm install' from the frontend directory."
}

if (-not (Test-Path -LiteralPath $backendEnvironment -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $environmentExample -PathType Leaf)) {
        Stop-WithError "Neither backend\.env nor .env.example exists."
    }
    Copy-Item -LiteralPath $environmentExample -Destination $backendEnvironment
    Write-Success "Created backend\.env from the safe example configuration."
}

Write-Success "Python environment, npm, frontend packages, and configuration are present."
Write-Host ""

$apiHealth = Get-JsonResponse -Url $apiHealthUrl
if ($apiHealth -and $apiHealth.status -eq "ok") {
    Write-Success "Backend is already running on port 8000."
}
else {
    if (Test-PortListening -Port 8000) {
        Stop-WithError "Port 8000 is occupied by a service that is not a healthy Traceveil API."
    }

    Write-Step "Starting the backend in a labeled service console..."
    $backendCommand = "title Traceveil Backend && cd /d `"$backendDirectory`" && `"$pythonExecutable`" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
    Start-Process -FilePath $env:ComSpec -ArgumentList @("/k", $backendCommand) -WorkingDirectory $backendDirectory | Out-Null

    if (-not (Wait-Until -Description "Backend" -Condition {
        $health = Get-JsonResponse -Url $apiHealthUrl
        return $health -and $health.status -eq "ok"
    })) {
        Stop-WithError "Backend startup failed. Review the Traceveil Backend console."
    }
    Write-Success "Backend API is responding."
}

$frontendReady = Test-Frontend
if ($frontendReady) {
    Write-Success "Frontend is already running on port 5173."
}
else {
    if (Test-PortListening -Port 5173) {
        Stop-WithError "Port 5173 is occupied by a service that is not a healthy Traceveil frontend."
    }

    Write-Step "Starting the frontend in a labeled service console..."
    $frontendCommand = "title Traceveil Frontend && cd /d `"$frontendDirectory`" && npm.cmd run dev -- --host 127.0.0.1 --port 5173"
    Start-Process -FilePath $env:ComSpec -ArgumentList @("/k", $frontendCommand) -WorkingDirectory $frontendDirectory | Out-Null

    if (-not (Wait-Until -Description "Frontend" -Condition { Test-Frontend })) {
        Stop-WithError "Frontend startup failed. Review the Traceveil Frontend console."
    }
    Write-Success "Frontend is responding."
}

Write-Host ""
Write-Host "Verifying Traceveil services..." -ForegroundColor White

$verifiedApi = Get-JsonResponse -Url $apiHealthUrl
if (-not $verifiedApi -or $verifiedApi.status -ne "ok") {
    Stop-WithError "The API health check failed after startup."
}
Write-Success "API health: operational"

$databaseHealth = Get-JsonResponse -Url $databaseHealthUrl
if (-not $databaseHealth -or $databaseHealth.status -ne "ok") {
    Stop-WithError "The database is unavailable. The API is running in degraded mode; inspect the Backend console and backend\.env."
}
Write-Success "Database health: operational"

if (-not (Test-Frontend)) {
    Stop-WithError "The frontend stopped responding after startup."
}
Write-Success "Frontend health: operational"

$aiHealth = Get-JsonResponse -Url $aiHealthUrl
if ($aiHealth -and $aiHealth.status -eq "ok") {
    Write-Success "Optional Ollama health: operational"
}
else {
    Write-WarningMessage "Ollama is offline or unavailable; core Traceveil features remain operational."
}

Write-Host ""
Write-Host "Traceveil is ready." -ForegroundColor Green
Write-Host "  App:      $applicationUrl" -ForegroundColor White
Write-Host "  API:      $apiHealthUrl" -ForegroundColor DarkGray
Write-Host "  Database: $databaseHealthUrl" -ForegroundColor DarkGray

if (-not $NoBrowser) {
    Write-Step "Opening Traceveil in the default browser..."
    Start-Process $applicationUrl | Out-Null
}

exit 0
