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

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

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
streamlit run app.py
