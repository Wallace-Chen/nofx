# Trending Crypto Coins Scraper

Browser automation tool to fetch trending cryptocurrency coins from CoinGecko and save filtered symbols to a text file.

## Features

- ✅ Fetches trending coins from CoinGecko
- ✅ Filters by market cap (>= $1 billion)
- ✅ Excludes USD-pegged stablecoins
- ✅ Saves to text file (one symbol per line)
- ✅ Continuous polling support (default: 10 minutes)
- ✅ WebKit browser automation (Mac-optimized)

## Installation

### 1. Install Python Dependencies

```bash
cd telegram/trending_coins
pip install -r requirements.txt
```

### 2. Install Browser Binaries

```bash
playwright install webkit  # Mac (recommended)
# or
playwright install chromium  # Linux
```

## Usage

### Continuous Polling (Default: 10 minutes)

```bash
python3 trending_scraper.py
```

### Single Run (No Polling)

```bash
python3 trending_scraper.py --once
```

### Custom Interval

```bash
# Update every 5 minutes (300 seconds)
python3 trending_scraper.py --interval 300
```

### Custom Output File

```bash
python3 trending_scraper.py --output /path/to/coins.txt
```

### Debug Mode (Visible Browser)

```bash
python3 trending_scraper.py --headless false --verbose
```

### Background Mode

```bash
# Run in background
nohup python3 trending_scraper.py --interval 600 > trending.log 2>&1 &

# Check logs
tail -f trending.log

# Stop
pkill -f trending_scraper
```

## Output Format

The scraper saves filtered coin symbols to `trending_coins.txt` (by default), one trading pair per line. Each symbol is automatically appended with "USDT" for trading pair format:

```
BTCUSDT
ETHUSDT
SOLUSDT
AVAXUSDT
```

Note: The symbols are saved as trading pairs (e.g., ASTERUSDT) ready for use with Binance and other exchanges.

## Filtering Rules

The scraper applies two filters:

1. **Market Cap Filter**: Only includes coins with market cap >= $1 billion
   - Coins without market cap data are included (benefit of doubt)

2. **Symbol Filter**: Excludes any symbol containing "USD"
   - Filters out stablecoins like USDT, USDC, BUSD, etc.

## Examples

### Example 1: Single Run

```bash
python3 trending_scraper.py --once --verbose
```

Output:
```
[2025-11-03 08:42:03] [INFO] Trending Crypto Coins Scraper
[2025-11-03 08:42:03] [INFO] Output file: trending_coins.txt
[2025-11-03 08:42:03] [INFO] Min market cap: $1.0B
[2025-11-03 08:42:03] [INFO] Mode: Single run
[2025-11-03 08:42:14] [INFO] ✓ Fetched 7 trending coins
[2025-11-03 08:42:14] [INFO] Filtered 2 coins (from 7 total)
[2025-11-03 08:42:14] [INFO] ✓ Saved 2 symbols to trending_coins.txt
[2025-11-03 08:42:14] [INFO] Trading pairs: ASTERUSDT, ZECUSDT
```

### Example 2: Continuous Polling

```bash
python3 trending_scraper.py --interval 300
```

This will fetch and update the coin list every 5 minutes.

### Example 3: Integration with Trading Bot

```python
# Read trending trading pairs
def get_trending_pairs():
    """Read trending trading pairs from file"""
    with open('telegram/trending_coins/trending_coins.txt', 'r') as f:
        return [line.strip() for line in f if line.strip()]

# Use in trading logic
trending_pairs = get_trending_pairs()
for pair in trending_pairs:
    # Trading pairs are in USDT format, ready for Binance
    print(f"Monitoring {pair}...")
    # Example: ASTERUSDT, ZECUSDT, etc.
```

The file already contains symbols in trading pair format (e.g., ASTERUSDT), so you can use them directly with exchange APIs.

## How It Works

The scraper follows these steps:

1. **Launches WebKit browser** (headless by default)
2. **Navigates** to https://www.coingecko.com/en/highlights/trending-crypto
3. **Scrolls down the page** 3 times (1000px each) to trigger lazy-loading of additional content
4. **Extracts JSON data** embedded in page HTML (data-search-trending attribute)
5. **Parses trending coins** with symbol, name, and market cap from the JSON
6. **Applies filters**:
   - Excludes symbols containing "USD" (stablecoins)
   - Excludes coins with market cap < $1 billion
7. **Appends "USDT"** to each filtered symbol for trading pair format (e.g., ASTER → ASTERUSDT)
8. **Saves trading pairs** to text file (one per line)
9. **Repeats** at specified interval (if polling mode)

**Note**: The scrolling feature ensures that lazy-loaded content is fetched, potentially capturing more trending coins beyond the initially visible ones.

## Troubleshooting

### Browser Not Found

```bash
python3 -m playwright install webkit
```

### Permission Denied

```bash
chmod +x trending_scraper.py
```

### No Coins Fetched

1. Check internet connection
2. Verify CoinGecko is accessible:
   ```bash
   curl -I https://www.coingecko.com
   ```
3. Run in visible mode to debug:
   ```bash
   python3 trending_scraper.py --once --headless false --verbose
   ```
4. CoinGecko may have changed their HTML structure - check logs

### Rate Limiting

If CoinGecko blocks requests:
- Increase polling interval (e.g., 15+ minutes)
- Add delays between requests
- Consider using CoinGecko API instead

## CoinGecko HTML Structure

The scraper looks for trending coins in the page structure. If CoinGecko updates their layout, you may need to adjust the selectors in `trending_scraper.py`:

```python
# Current selectors (lines ~150-160)
symbol_elem = row.query_selector('.coin-symbol, [data-coin-symbol], .tw-uppercase')
market_cap_elem = row.query_selector('[data-target="market_cap"], .market-cap, td:has-text("$")')
```

## Scheduling with Cron

```bash
# Edit crontab
crontab -e

# Run every 10 minutes
*/10 * * * * cd /path/to/nofx/telegram/trending_coins && python3 trending_scraper.py --once >> cron.log 2>&1
```

## Performance

- **Browser Startup**: ~1-2 seconds
- **Page Load**: ~2-3 seconds
- **Data Extraction**: ~1 second
- **Total Time**: ~5-8 seconds per run
- **Memory Usage**: ~200-250 MB (browser)

## Limitations

1. **Browser Required**: Needs Playwright browser binaries
2. **Rate Limits**: Respect CoinGecko's rate limits
3. **HTML Changes**: May break if CoinGecko updates their page structure
4. **Market Cap Data**: Not all coins have market cap data available

## Alternatives

If browser automation is too heavy:

1. **CoinGecko API**: Use official API (requires API key)
   ```bash
   curl "https://api.coingecko.com/api/v3/search/trending"
   ```

2. **RSS Feeds**: Subscribe to crypto news feeds

3. **WebSocket Streams**: Real-time price/volume data

## Support

If you encounter issues:

1. Check logs with `--verbose` flag
2. Test with visible browser `--headless false`
3. Verify CoinGecko page structure hasn't changed
4. Check Playwright version compatibility

## License

Same as parent project (NOFX).
