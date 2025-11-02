#!/bin/bash

echo "🚀 Setting up Economic Calendar Integration"
echo ""

# 1. Create economic calendar database
echo "📅 Step 1: Creating economic calendar database..."
cd world/经济日历

if [ ! -f "economic_calendar_minimal.py" ]; then
    echo "❌ Error: economic_calendar_minimal.py not found in world/经济日历/"
    exit 1
fi

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Running data collection script..."
python economic_calendar_minimal.py

if [ ! -f "economic_calendar.db" ]; then
    echo "❌ Error: Failed to create economic_calendar.db"
    exit 1
fi

echo "✓ Economic calendar database created"
cd ../..

# 2. Check config.db exists
echo ""
echo "📋 Step 2: Checking for config.db..."
if [ ! -f "config.db" ]; then
    echo "❌ config.db not found."
    echo ""
    echo "Please run the system once first to create config.db:"
    echo "  go run main.go"
    echo "  OR"
    echo "  ./start.sh start"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "✓ Found config.db"

# 3. Get trader ID
echo ""
echo "📋 Step 3: Available traders:"
echo ""
sqlite3 -column -header config.db "SELECT id, name FROM traders;"

echo ""
read -p "Enter trader ID to configure (or 'all' for all traders): " TRADER_ID

if [ -z "$TRADER_ID" ]; then
    echo "❌ No trader ID provided"
    exit 1
fi

# 4. Update configuration
echo ""
echo "🔧 Step 4: Updating configuration..."

if [ "$TRADER_ID" = "all" ]; then
    sqlite3 config.db <<SQL
UPDATE traders
SET economic_calendar_db = 'world/经济日历/economic_calendar.db',
    economic_calendar_hours = 24,
    economic_calendar_importance = '高';
SQL
    echo "✓ Updated all traders"
else
    sqlite3 config.db <<SQL
UPDATE traders
SET economic_calendar_db = 'world/经济日历/economic_calendar.db',
    economic_calendar_hours = 24,
    economic_calendar_importance = '高'
WHERE id = '$TRADER_ID';
SQL
    echo "✓ Updated trader: $TRADER_ID"
fi

# 5. Verify
echo ""
echo "✅ Step 5: Configuration summary:"
echo ""
sqlite3 -column -header config.db "
SELECT
    id,
    name,
    economic_calendar_db as 'database',
    economic_calendar_hours as 'hours',
    economic_calendar_importance as 'importance'
FROM traders
WHERE economic_calendar_db != '';"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Restart your trading system to apply changes"
echo "  2. Check logs for: ✓ 已加载 X 个经济日历事件"
echo "  3. Run the economic calendar script periodically to update events:"
echo "     cd world/经济日历 && python economic_calendar_minimal.py"
echo ""
