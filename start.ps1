# OurCents - Quick Start Script for Windows

Write-Host "🏦 OurCents - Family Expense Tracker" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "⚠️  .env file not found. Creating from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✅ Created .env file. Please edit it and add your OpenAI API key." -ForegroundColor Green
    Write-Host ""
    Write-Host "Set OPENAI_API_KEY in .env before continuing." -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Press Enter to continue after adding your API key"
}

$venvDir = ".venv"

if (-not (Test-Path $venvDir) -and (Test-Path "venv")) {
    $venvDir = "venv"
}

# Check if virtual environment exists
if (-not (Test-Path $venvDir)) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    $venvDir = ".venv"
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& ".\$venvDir\Scripts\Activate.ps1"

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
& ".\$venvDir\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\$venvDir\Scripts\python.exe" -m pip install -r requirements.txt --quiet

# Create data directories
Write-Host "📁 Creating data directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path data\receipts | Out-Null
New-Item -ItemType Directory -Force -Path data\temp | Out-Null
New-Item -ItemType Directory -Force -Path logs | Out-Null

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Starting OurCents..." -ForegroundColor Cyan
Write-Host ""

# Run the app
& ".\$venvDir\Scripts\python.exe" -m streamlit run app.py
