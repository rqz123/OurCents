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

# Check if virtual environment exists
if (-not (Test-Path venv)) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

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
streamlit run app.py
