#!/bin/bash

# Simple Person Counter - 24 Hour Recount Window
# Start script

cd /Users/biswajitsahu/Desktop/marketing-campaign-analysis/count_unique_person/count_unique_person

echo "======================================================"
echo "SIMPLIFIED PERSON COUNTER - 24 Hour Recount"
echo "======================================================"
echo ""

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: bash utilities/setup.sh"
    exit 1
fi

source .venv/bin/activate

echo "✅ Virtual environment activated"
echo ""
echo "🚀 Starting Person Counter..."
echo "   - Counts unique people entering frame"
echo "   - Captures photos automatically"
echo "   - Does NOT recount same person for 24 hours"
echo "   - After 24 hours can be counted again"
echo "   - Results organized by date"
echo ""
echo "⏹️  Press 'q' to quit"
echo ""

python applications/simple_counter.py

