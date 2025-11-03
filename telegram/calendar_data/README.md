# Economic Calendar Scraper (Browser Automation)

This tool uses browser automation (Playwright) to fetch economic calendar data from cn.investing.com, bypassing the 403 blocking that affects direct HTTP requests.

## Why Browser Automation?

Direct HTTP requests to cn.investing.com are blocked with 403 Forbidden errors due to:
- Cloudflare protection
- Anti-bot detection
- Rate limiting

Browser automation solves this by:
- ✅ Simulating real browser behavior
- ✅ Handling JavaScript rendering
- ✅ Managing cookies and sessions automatically
- ✅ Bypassing anti-bot protection

## Features

- **Browser Automation**: Uses Playwright (Chromium) to scrape data
- **Same Database Format**: Compatible with existing `经济日历` database structure
- **Headless Mode**: Runs in background without visible browser
- **Continuous Polling**: Supports scheduled data updates
- **Robust Parsing**: Handles cn.investing.com HTML structure

## Installation

### 1. Install Python Dependencies

```bash
cd telegram/calendar_data
pip install -r requirements.txt
```

### 2. Install Browser Binaries

Playwright needs to download Chromium browser:

```bash
playwright install chromium
```

This will download ~300MB of browser binaries.

## Usage

### Single Run (Fetch Once)

```bash
python3 calendar_scraper.py
```

### Custom Date Range

```bash
# Fetch 14 days ahead
python3 calendar_scraper.py --days 14
```

### Continuous Polling

```bash
# Update every 5 minutes (300 seconds)
python3 calendar_scraper.py --interval 300
```

### Debug Mode (Visible Browser)

```bash
# Show browser window for debugging
python3 calendar_scraper.py --headless false
```

### Verbose Logging

```bash
python3 calendar_scraper.py --verbose
```

### Background Mode

```bash
# Run in background
nohup python3 calendar_scraper.py --interval 300 > calendar.log 2>&1 &

# Check logs
tail -f calendar.log

# Stop
pkill -f calendar_scraper
```

## Database Structure

The scraper creates `economic_calendar.db` with this schema:

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,              -- Format: DD/MM/YYYY
    time TEXT,                        -- Format: HH:MM or "全天"
    zone TEXT,                        -- Country/region
    currency TEXT,                    -- Currency code (USD, EUR, etc.)
    event TEXT NOT NULL,              -- Event name
    importance TEXT,                  -- "高", "中", "低"
    actual TEXT,                      -- Actual value
    forecast TEXT,                    -- Forecasted value
    previous TEXT,                    -- Previous value
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(date, time, zone, event)
);
```

## Integration with Trading System

To use with the NOFX trading system:

### 1. Update System Configuration

Edit `config.json`:

```json
{
  "economic_calendar": {
    "enabled": true,
    "db_path": "telegram/calendar_data/economic_calendar.db",
    "hours_ahead": 24,
    "min_importance": "高"
  }
}
```

### 2. Run Setup Script

```bash
cd ../..  # Back to project root
./setup_economic_calendar.sh
```

Select the trader(s) to configure when prompted.

### 3. Restart Trading System

```bash
go run main.go
```

Look for log message:
```
✓ 已加载 X 个经济日历事件（未来24小时，高重要性及以上）
```

## Comparison with HTTP Version

| Feature | HTTP Version | Browser Automation |
|---------|-------------|-------------------|
| Speed | ⚡ Fast (~1s) | 🐢 Slower (~5-10s) |
| Reliability | ❌ 403 Blocked | ✅ Works |
| Resource Usage | Low | Higher (browser) |
| Setup Complexity | Simple | Moderate |
| Maintenance | Easy | Browser updates needed |

**Recommendation**: Use browser automation since HTTP is blocked.

## Troubleshooting

### "playwright: command not found"

```bash
pip install playwright
playwright install chromium
```

### Browser Download Fails

Try manual installation:

```bash
python -m playwright install chromium --with-deps
```

### No Events Fetched

1. Check internet connection
2. Try visible mode to see what's happening:
   ```bash
   python3 calendar_scraper.py --headless false --verbose
   ```
3. Check if cn.investing.com is accessible in your region
4. Consider using a VPN if site is blocked

### TimeoutError

Increase timeouts by editing `calendar_scraper.py`:

```python
page.goto(url, timeout=60000)  # Increase to 60 seconds
page.wait_for_selector('#economicCalendarData', timeout=30000)
```

### Memory Issues

Browser automation uses more memory. For production:

```bash
# Limit memory usage
export PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers
```

## Advanced Configuration

### Environment Variables

Create `.env` file:

```bash
DATABASE_URL=sqlite+pysqlite:///./economic_calendar.db
```

### Proxy Support

To use a proxy with Playwright, edit `calendar_scraper.py`:

```python
context = browser.new_context(
    user_agent='...',
    proxy={
        "server": "http://proxy.example.com:8080",
        "username": "user",
        "password": "pass"
    }
)
```

### Scheduling with Cron

```bash
# Edit crontab
crontab -e

# Run every hour
0 * * * * cd /path/to/nofx/telegram/calendar_data && python3 calendar_scraper.py >> calendar_cron.log 2>&1
```

## Performance Optimization

### 1. Reuse Browser Context

For frequent polling, consider keeping browser open between runs.

### 2. Selective Updates

Only fetch recent changes instead of full calendar:

```bash
python3 calendar_scraper.py --days 3  # Only next 3 days
```

### 3. Headless Mode

Always use headless in production (default):

```bash
python3 calendar_scraper.py --headless true
```

## Maintenance

### Update Playwright

```bash
pip install --upgrade playwright
playwright install chromium
```

### Database Cleanup

```bash
# Remove old events (older than 30 days)
sqlite3 economic_calendar.db "DELETE FROM events WHERE date < date('now', '-30 days');"
```

## Support

If you encounter issues:

1. Check logs with `--verbose` flag
2. Test with visible browser `--headless false`
3. Verify cn.investing.com is accessible
4. Check Playwright version compatibility

## License

Same as parent project (NOFX).
