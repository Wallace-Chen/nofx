#!/usr/bin/env python3
"""
Trending Crypto Coins Scraper with Browser Automation
Fetches trending coins from CoinGecko and saves filtered symbols

Features:
- ✅ Browser automation to fetch trending coins
- ✅ Filter by market cap (>= $1B) and exclude USD-pegged coins
- ✅ Save to text file (one symbol per line)
- ✅ Continuous polling support
- ✅ Headless mode for production

Dependencies:
    pip install playwright
    playwright install webkit  # Use webkit on Mac, chromium on Linux

Usage:
    # Default run (10 minute interval)
    python3 trending_scraper.py

    # Single run (no polling)
    python3 trending_scraper.py --once

    # Custom interval
    python3 trending_scraper.py --interval 300

    # Debug mode (visible browser)
    python3 trending_scraper.py --headless false --verbose
"""

import os
import sys
import time
import signal
import argparse
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================================
# Dependency Check
# ============================================================================

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install with: pip install playwright")
    print("Then run: playwright install webkit")
    sys.exit(1)

# ============================================================================
# Configuration
# ============================================================================

parser = argparse.ArgumentParser(description='Trending Crypto Coins Scraper')
parser.add_argument('--interval', type=int, default=600, help='Polling interval in seconds (default: 600 = 10 minutes)')
parser.add_argument('--once', action='store_true', help='Run once and exit (no polling)')
parser.add_argument('--headless', type=str, default='true', help='Run browser in headless mode (default: true)')
parser.add_argument('--verbose', action='store_true', help='Verbose logging')
parser.add_argument('--output', type=str, default='trending_coins.txt', help='Output file path (default: trending_coins.txt)')
args = parser.parse_args()

# Configuration
OUTPUT_FILE = args.output
HEADLESS = args.headless.lower() in ('true', '1', 'yes')
VERBOSE = args.verbose
POLL_INTERVAL = None if args.once else args.interval
MIN_MARKET_CAP = 1_000_000_000  # 1 billion USD
COINGECKO_URL = 'https://www.coingecko.com/en/highlights/trending-crypto'

# Global state
running = True
fetch_count = 0

# ============================================================================
# Logging
# ============================================================================

def log(message: str, level: str = "INFO"):
    """Simple logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def verbose_log(message: str):
    """Verbose logging (only if enabled)"""
    if VERBOSE:
        log(message, "DEBUG")

# ============================================================================
# Browser Automation
# ============================================================================

def parse_market_cap(market_cap_str: str) -> Optional[float]:
    """Parse market cap string like '$1.2B' or '$500M' to float"""
    if not market_cap_str or market_cap_str == 'N/A':
        return None

    try:
        # Remove '$' and spaces
        clean_str = market_cap_str.replace('$', '').replace(',', '').strip()

        # Handle B (billions), M (millions), K (thousands)
        multiplier = 1
        if clean_str.endswith('B'):
            multiplier = 1_000_000_000
            clean_str = clean_str[:-1]
        elif clean_str.endswith('M'):
            multiplier = 1_000_000
            clean_str = clean_str[:-1]
        elif clean_str.endswith('K'):
            multiplier = 1_000
            clean_str = clean_str[:-1]

        value = float(clean_str) * multiplier
        return value
    except Exception as e:
        verbose_log(f"Failed to parse market cap '{market_cap_str}': {e}")
        return None

def fetch_trending_coins() -> List[Dict]:
    """Fetch trending coins using browser automation"""
    global fetch_count

    try:
        log("Fetching trending coins from CoinGecko...")
        coins = []

        with sync_playwright() as p:
            # Launch browser (WebKit works better on Mac)
            verbose_log("Launching browser...")
            browser = p.webkit.launch(headless=HEADLESS)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            try:
                # Navigate to trending crypto page
                verbose_log(f"Navigating to {COINGECKO_URL}")
                page.goto(COINGECKO_URL, timeout=30000, wait_until='domcontentloaded')

                # Wait for content to load
                verbose_log("Waiting for trending coins data...")
                time.sleep(2)  # Give time for initial content

                # Scroll down to load more content
                verbose_log("Scrolling down to load more coins...")
                for i in range(3):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(1)

                # Scroll back to top
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1)

                # CoinGecko embeds trending data in a data attribute as JSON
                verbose_log("Extracting coin data from JSON...")

                # Try to extract data-search-trending attribute
                import json
                import re

                # Get page content
                html_content = page.content()

                # Find the data-search-trending JSON
                match = re.search(r'data-search-trending="([^"]+)"', html_content)

                if match:
                    # Decode HTML entities
                    import html as html_module
                    json_str = html_module.unescape(match.group(1))

                    # Parse JSON
                    trending_data = json.loads(json_str)

                    # Extract coins from the JSON
                    if 'coins' in trending_data:
                        verbose_log(f"Found {len(trending_data['coins'])} trending coins in JSON")

                        for coin_data in trending_data['coins']:
                            try:
                                item = coin_data.get('item', {})
                                data = item.get('data', {})

                                symbol = item.get('symbol', '').upper()
                                name = item.get('name', 'Unknown')
                                market_cap_str = data.get('market_cap', 'N/A')

                                if not symbol:
                                    verbose_log(f"Skipping coin - no symbol")
                                    continue

                                # Parse market cap
                                market_cap = parse_market_cap(market_cap_str) if market_cap_str else None

                                coin = {
                                    'symbol': symbol,
                                    'name': name,
                                    'market_cap': market_cap,
                                    'market_cap_str': market_cap_str
                                }

                                coins.append(coin)
                                verbose_log(f"Found: {symbol} ({name}) - Market Cap: {market_cap_str}")

                            except Exception as e:
                                verbose_log(f"Error parsing coin from JSON: {str(e)[:50]}")
                                continue
                    else:
                        log("No 'coins' key in trending data JSON", "WARN")
                else:
                    log("Could not find trending data JSON in page", "WARN")

                page.close()
                context.close()
                browser.close()

            except PlaywrightTimeout as e:
                log(f"Timeout loading page: {e}", "ERROR")
                browser.close()
                return []
            except Exception as e:
                log(f"Error during scraping: {str(e)[:100]}", "ERROR")
                browser.close()
                return []

        fetch_count += 1
        log(f"✓ Fetched {len(coins)} trending coins")
        return coins

    except Exception as e:
        log(f"Fatal error: {str(e)}", "ERROR")
        return []

def filter_coins(coins: List[Dict]) -> List[str]:
    """Filter coins by market cap and symbol criteria"""
    if not coins:
        return []

    filtered = []

    for coin in coins:
        symbol = coin.get('symbol', '')
        market_cap = coin.get('market_cap')

        # Filter 1: Exclude symbols containing 'USD'
        if 'USD' in symbol.upper():
            verbose_log(f"Filtered out {symbol} - contains 'USD'")
            continue

        # Filter 2: Exclude coins with market cap < 1B (if market cap is available)
        if market_cap is not None and market_cap < MIN_MARKET_CAP:
            verbose_log(f"Filtered out {symbol} - market cap ${market_cap/1e9:.2f}B < $1B")
            continue

        # If market cap is not available, we'll include it (since we can't verify)
        if market_cap is None:
            verbose_log(f"Including {symbol} - market cap not available (assuming OK)")

        filtered.append(symbol)

    log(f"Filtered {len(filtered)} coins (from {len(coins)} total)")
    return filtered

def save_to_file(symbols: List[str]) -> bool:
    """Save symbols to text file, one per line, with USDT appended"""
    if not symbols:
        log("No symbols to save", "WARN")
        return False

    try:
        with open(OUTPUT_FILE, 'w') as f:
            for symbol in symbols:
                # Append USDT to each symbol for trading pair format
                trading_pair = f"{symbol}USDT"
                f.write(f"{trading_pair}\n")

        log(f"✓ Saved {len(symbols)} symbols to {OUTPUT_FILE}")

        # Also log the symbols with USDT appended
        trading_pairs = [f"{s}USDT" for s in symbols]
        log(f"Trading pairs: {', '.join(trading_pairs)}")

        return True
    except Exception as e:
        log(f"Error saving to file: {e}", "ERROR")
        return False

# ============================================================================
# Main Program
# ============================================================================

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    global running
    log("Received stop signal, exiting...", "INFO")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def update_data():
    """Fetch and update data"""
    log("=" * 70)
    log("Starting data collection...")

    coins = fetch_trending_coins()

    if coins:
        filtered_symbols = filter_coins(coins)
        if filtered_symbols:
            save_to_file(filtered_symbols)
            log(f"📊 Total fetches: {fetch_count}")
        else:
            log("⚠ No coins passed filters", "WARN")
    else:
        log("⚠ No coins fetched", "WARN")

    return len(coins)

def main():
    """Main entry point"""
    log("=" * 70)
    log("Trending Crypto Coins Scraper")
    log("=" * 70)
    log(f"Output file: {OUTPUT_FILE}")
    log(f"Min market cap: ${MIN_MARKET_CAP/1e9:.1f}B")
    log(f"Headless mode: {HEADLESS}")

    if POLL_INTERVAL:
        log(f"Polling interval: {POLL_INTERVAL}s")
    else:
        log(f"Mode: Single run")

    log("=" * 70)

    try:
        # First run
        update_data()

        if POLL_INTERVAL:
            # Continuous polling mode
            log("Starting continuous polling mode...")

            while running:
                log(f"Sleeping for {POLL_INTERVAL}s...")

                # Sleep in small increments to allow graceful shutdown
                for _ in range(POLL_INTERVAL):
                    if not running:
                        break
                    time.sleep(1)

                if running:
                    update_data()

            log("✓ Polling stopped")
        else:
            # Single run mode
            log("✓ Single run complete")

    except Exception as e:
        log(f"Fatal error: {e}", "ERROR")
        return 1

    log("Program exited")
    return 0

if __name__ == "__main__":
    sys.exit(main())
