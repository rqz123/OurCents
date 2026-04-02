#!/bin/bash

# OurCents - Quick start script

echo "🏦 OurCents - Family Expense Tracker"
echo "===================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it and add your OpenAI API key."
    echo ""
    echo "Set OPENAI_API_KEY in .env before continuing."
    echo ""
    read -p "Press Enter to continue after adding your API key..."
fi

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ] && [ -d "venv" ]; then
    VENV_DIR="venv"
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
    VENV_DIR=".venv"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "📥 Installing dependencies..."
"$VENV_DIR/bin/python" -m pip install -q --upgrade pip
"$VENV_DIR/bin/python" -m pip install -q -r requirements.txt

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/receipts
mkdir -p data/temp
mkdir -p logs

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting OurCents..."
echo ""

# Run the app
"$VENV_DIR/bin/python" -m streamlit run app.py
