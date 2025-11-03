# Crypto News Scraper

Browser automation tool to fetch cryptocurrency news from TheBlockBeats and save to SQLite database for AI trading context.

## Features

- ✅ Fetches crypto news from TheBlockBeats
- ✅ Saves to SQLite database (title, content, timestamp, importance)
- ✅ Timezone conversion: Beijing time → Texas time (US/Central)
- ✅ Duplicate detection using content hashing
- ✅ Automatic database cleanup (removes old news when > 1 MB)
- ✅ Continuous polling support
- ✅ Pagination/scroll support (fetch up to 20 news items)
- ✅ WebKit browser automation (Mac-optimized)

## Installation

### 1. Install Python Dependencies

```bash
cd telegram/news
pip install -r requirements.txt
```

### 2. Install Browser Binaries

```bash
playwright install webkit  # Mac (recommended)
# or
playwright install chromium  # Linux
```

## Usage

### Single Run (Fetch Once)

```bash
python3 news_scraper.py
```

### Continuous Polling (5 minutes)

```bash
python3 news_scraper.py --interval 300
```

### Custom Options

```bash
# Custom database path
python3 news_scraper.py --db /path/to/news.db

# Fetch more news (default: 20)
python3 news_scraper.py --max-news 30

# Debug mode (visible browser)
python3 news_scraper.py --headless false --verbose
```

### Background Mode

```bash
# Run in background with continuous polling
nohup python3 news_scraper.py --interval 300 > news.log 2>&1 &

# Check logs
tail -f news.log

# Stop
pkill -f news_scraper
```

## Database Schema

The scraper creates `news.db` with this schema:

```sql
CREATE TABLE news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    timestamp TEXT NOT NULL,
    importance TEXT,  -- 'low', 'medium', 'high', 'critical'
    hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX idx_timestamp ON news(timestamp);
CREATE INDEX idx_hash ON news(hash);
CREATE INDEX idx_created_at ON news(created_at);
```

### Query Examples

```bash
# View latest 10 news
sqlite3 news.db "SELECT title, timestamp, importance FROM news ORDER BY created_at DESC LIMIT 10;"

# Count news by importance
sqlite3 news.db "SELECT importance, COUNT(*) FROM news GROUP BY importance;"

# Get high importance news from last 24 hours
sqlite3 news.db "SELECT title, content FROM news WHERE importance='high' AND datetime(created_at) > datetime('now', '-1 day');"

# Check database size
ls -lh news.db
```

## Features in Detail

### 1. Duplicate Detection

Uses MD5 hash of `title + first 100 chars of content` to detect duplicates:
- Prevents re-saving the same news
- Uses UNIQUE constraint on hash field
- Logs duplicate count

### 2. Timezone Conversion

Automatically converts timestamps from Beijing time to Texas time (US/Central):
- **Source**: TheBlockBeats timestamps are in Beijing time (UTC+8)
- **Target**: US Central Time (UTC-6 CST / UTC-5 CDT)
- **Time difference**: 14 hours behind (CST) or 13 hours behind (CDT)
- **Example**: Beijing 23:46 → Texas 09:46 (same day)

This ensures all news timestamps align with your local trading time for better context.

### 3. Database Size Management

Automatically cleans up when database exceeds 1 MB:
- Deletes oldest 30% of news items
- Runs VACUUM to reclaim space
- Logs cleanup actions

### 4. Importance Detection

Automatically detects importance level:
- **critical**: Urgent/critical tags
- **high**: Important tags, red colors
- **medium**: Default for most news
- **low**: Low priority tags

Detection looks for:
- Badge/tag elements with importance indicators
- CSS classes with urgency keywords
- Color indicators (red = high importance)

### 5. Pagination Support

Handles different pagination methods:
- Scrolls page 3 times to trigger lazy loading
- Clicks "Load More" / "加载更多" buttons
- Fetches up to 20 news items per run (configurable)

## Integration with Trading System

### Reading News from Database

```python
import sqlite3

def get_recent_news(hours=24, min_importance='medium'):
    """Get recent important news for AI context"""
    conn = sqlite3.connect('telegram/news/news.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, content, timestamp, importance
        FROM news
        WHERE datetime(created_at) > datetime('now', '-{} hours')
        AND importance IN ('high', 'critical')
        ORDER BY created_at DESC
        LIMIT 10
    """.format(hours))

    news = cursor.fetchall()
    conn.close()

    return news

# Use in trading logic
recent_news = get_recent_news(hours=24)
for title, content, timestamp, importance in recent_news:
    print(f"[{importance.upper()}] {title}")
    # Feed to AI for context
```

### Formatting for AI Context

```python
def format_news_for_ai(news_list):
    """Format news for AI trading prompt"""
    if not news_list:
        return "No recent news."

    formatted = "Recent Crypto News:\n\n"
    for i, (title, content, timestamp, importance) in enumerate(news_list, 1):
        formatted += f"{i}. [{importance.upper()}] {title}\n"
        formatted += f"   Time: {timestamp}\n"
        if content:
            formatted += f"   Summary: {content[:200]}...\n"
        formatted += "\n"

    return formatted

# Add to AI prompt
news_context = format_news_for_ai(recent_news)
ai_prompt = f"{news_context}\n\nBased on the above news, analyze market sentiment and suggest trading strategies..."
```

## Examples

### Example 1: Single Run

```bash
python3 news_scraper.py --verbose
```

Output:
```
[2025-11-03 09:00:00] [INFO] ======================================================================
[2025-11-03 09:00:00] [INFO] Crypto News Scraper
[2025-11-03 09:00:00] [INFO] Database: news.db
[2025-11-03 09:00:00] [INFO] Max news per run: 20
[2025-11-03 09:00:05] [INFO] ✓ Fetched 18 news items
[2025-11-03 09:00:05] [INFO] ✓ Saved 15 new items, skipped 3 duplicates
[2025-11-03 09:00:05] [INFO] 📊 Total fetches: 1, DB size: 45.2 KB
```

### Example 2: Continuous Polling

```bash
python3 news_scraper.py --interval 300
```

This will fetch news every 5 minutes continuously.

### Example 3: Check Database

```bash
# Count total news
sqlite3 news.db "SELECT COUNT(*) FROM news;"

# Show recent high-importance news
sqlite3 news.db "SELECT title, timestamp FROM news WHERE importance='high' ORDER BY created_at DESC LIMIT 5;"
```

## Troubleshooting

### Browser Not Found

```bash
python3 -m playwright install webkit
```

### No News Fetched

1. Check internet connection
2. Verify TheBlockBeats is accessible:
   ```bash
   curl -I https://www.theblockbeats.info
   ```
3. Run in visible mode to debug:
   ```bash
   python3 news_scraper.py --headless false --verbose
   ```
4. Website structure may have changed - check selectors

### Database Locked

If you get "database is locked" error:
```bash
# Close any other processes accessing the database
lsof news.db

# Or use a different database file
python3 news_scraper.py --db news_backup.db
```

### Database Growing Too Fast

Reduce max news count:
```bash
python3 news_scraper.py --max-news 10
```

## Performance

- **Browser Startup**: ~1-2 seconds
- **Page Load**: ~3-5 seconds
- **Scrolling/Pagination**: ~4-5 seconds
- **Data Extraction**: ~1-2 seconds
- **Total Time**: ~10-15 seconds per run
- **Memory Usage**: ~200-250 MB (browser)
- **Database Size**: Auto-managed (< 1 MB)

## Scheduling with Cron

```bash
# Edit crontab
crontab -e

# Run every 5 minutes
*/5 * * * * cd /path/to/nofx/telegram/news && python3 news_scraper.py >> cron.log 2>&1
```

## Database Maintenance

### Manual Cleanup

```bash
# Delete news older than 7 days
sqlite3 news.db "DELETE FROM news WHERE datetime(created_at) < datetime('now', '-7 days');"

# Vacuum to reclaim space
sqlite3 news.db "VACUUM;"
```

### Backup

```bash
# Backup database
cp news.db news_backup_$(date +%Y%m%d).db

# Restore from backup
cp news_backup_20250103.db news.db
```

## Limitations

1. **Website Changes**: May break if TheBlockBeats updates HTML structure
2. **Rate Limiting**: Respect website's rate limits
3. **Browser Required**: Needs Playwright browser binaries
4. **Memory Usage**: Browser automation uses more memory than API calls

## Alternatives

If browser automation is too heavy:

1. **RSS Feed**: Check if TheBlockBeats provides RSS
2. **API**: Use official API if available
3. **Third-party APIs**: CryptoPanic, NewsAPI, etc.

## Support

If you encounter issues:

1. Check logs with `--verbose` flag
2. Test with visible browser `--headless false`
3. Verify website structure hasn't changed
4. Check Playwright version compatibility

## License

Same as parent project (NOFX).
