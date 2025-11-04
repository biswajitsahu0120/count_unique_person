#!/bin/bash

# Person Counter Setup Script for macOS/Linux

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../" && pwd)"

echo "🚀 Setting up Person Counter Application..."
echo ""

# Check Python version
echo "📍 Checking Python version..."
python3 --version

# Navigate to project root
cd "$PROJECT_ROOT"

# Create virtual environment
echo ""
echo "📍 Creating/Checking virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "📍 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo ""
echo "📍 Upgrading pip..."
python -m pip install --quiet --upgrade pip setuptools wheel

# Install requirements
echo ""
echo "📍 Installing dependencies (this may take a few minutes)..."
pip install --quiet -r utilities/requirements.txt

# Verify installation
echo ""
echo "📍 Verifying installation..."
python -c "import cv2; print('  ✅ OpenCV')" 2>/dev/null || echo "  ⚠️  OpenCV"
python -c "import torch; print('  ✅ PyTorch')" 2>/dev/null || echo "  ⚠️  PyTorch"
python -c "import ultralytics; print('  ✅ YOLOv8')" 2>/dev/null || echo "  ⚠️  YOLOv8"
python -c "import pandas; print('  ✅ Pandas')" 2>/dev/null || echo "  ⚠️  Pandas"

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎮 To run the application:"
echo "   1. Activate virtual environment: source .venv/bin/activate"
echo "   2. Run: python main.py"
echo "   3. Or run lite version directly: python applications/run_lite.py"
echo ""
echo "Press 'q' to quit the application"

