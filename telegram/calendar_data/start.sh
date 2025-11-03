#!/bin/bash

echo "🚀 Starting Economic Calendar Scraper"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "❌ pip not found. Please install pip."
    exit 1
fi

# Install dependencies if not already installed
if ! python3 -c "import playwright" &> /dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install -r requirements.txt

    echo "🌐 Installing Chromium browser..."
    playwright install chromium
fi

# Run the scraper
echo "🔄 Fetching economic calendar data..."
python3 calendar_scraper.py "$@"

echo ""
echo "✅ Done!"
