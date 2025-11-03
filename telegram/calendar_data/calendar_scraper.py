#!/usr/bin/env python3
"""
Economic Calendar Scraper with Browser Automation
Using Playwright to bypass 403 blocking from cn.investing.com

Features:
- ✅ Browser automation to bypass anti-bot protection
- ✅ Same database structure as economic_calendar_minimal.py
- ✅ Automatic data collection and storage
- ✅ Scheduling support
- ✅ Headless mode for production

Dependencies:
    pip install playwright pytz python-dotenv
    playwright install webkit  # Use webkit on Mac, chromium on Linux

Usage:
    # Default run (7 days ahead)
    python3 calendar_scraper.py

    # Custom days ahead
    python3 calendar_scraper.py --days 14

    # With visible browser (for debugging)
    python3 calendar_scraper.py --headless false

    # Continuous polling
    python3 calendar_scraper.py --interval 300
"""

import os
import sys
import time
import sqlite3
import signal
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from copy import deepcopy

# ============================================================================
# Dependency Check
# ============================================================================

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    import pytz
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install with: pip install playwright pytz python-dotenv")
    print("Then run: playwright install chromium")
    sys.exit(1)

load_dotenv()

# ============================================================================
# Configuration
# ============================================================================

parser = argparse.ArgumentParser(description='Economic Calendar Scraper (Browser Automation)')
parser.add_argument('--days', type=int, default=7, help='Days ahead to fetch (default: 7)')
parser.add_argument('--interval', type=int, default=None, help='Polling interval in seconds (default: one-time run)')
parser.add_argument('--headless', type=str, default='true', help='Run browser in headless mode (default: true)')
parser.add_argument('--verbose', action='store_true', help='Verbose logging')
args = parser.parse_args()

# Database configuration
DB_PATH = os.getenv('DATABASE_URL', './economic_calendar.db').replace('sqlite+pysqlite:///', '')
DAYS_AHEAD = args.days
HEADLESS = args.headless.lower() in ('true', '1', 'yes')
VERBOSE = args.verbose

# Polling configuration
POLL_INTERVAL = args.interval  # None = run once
running = True

# Data normalization constants
ALL_DAY_SENTINEL = "全天"
TENTATIVE_SENTINEL = "待定"
ALL_DAY_TOKENS = {"all day", "allday", "全天", "tentative"}
TENTATIVE_TOKENS = {"tentative", "待定", "tbd"}
IMPORTANCE_MAP = {"bull1": "高", "bull2": "中", "bull3": "低"}

# Counters
fetch_count = 0
db_write_count = 0

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
# Data Normalization
# ============================================================================

def normalize_time(raw: Optional[str]) -> str:
    """Normalize time field"""
    if raw is None:
        return ALL_DAY_SENTINEL
    value = str(raw).strip().lower()
    if value in ALL_DAY_TOKENS:
        return ALL_DAY_SENTINEL
    if value in TENTATIVE_TOKENS:
        return TENTATIVE_SENTINEL
    return raw.strip()

def normalize_text(raw: Optional[str]) -> Optional[str]:
    """Normalize text field"""
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None

def normalize_event_for_db(event: Dict) -> Dict:
    """Normalize event data for database"""
    normalized = deepcopy(event)
    normalized["date"] = normalize_text(event.get("date"))
    if not normalized["date"]:
        raise ValueError("event date is required")
    normalized["event"] = normalize_text(event.get("event"))
    if not normalized["event"]:
        raise ValueError("event name is required")
    normalized["time"] = normalize_time(event.get("time"))
    normalized["zone"] = normalize_text(event.get("zone"))
    normalized["currency"] = normalize_text(event.get("currency"))
    normalized["importance"] = normalize_text(event.get("importance"))
    return normalized

# ============================================================================
# Browser Automation
# ============================================================================

def fetch_calendar_with_browser(days_ahead: int = DAYS_AHEAD) -> List[Dict]:
    """Fetch economic calendar using browser automation"""
    global fetch_count

    try:
        # Calculate date range
        today = datetime.now()
        future_date = today + timedelta(days=days_ahead)
        from_date = today.strftime('%Y-%m-%d')
        to_date = future_date.strftime('%Y-%m-%d')

        log(f"Fetching calendar data from {from_date} to {to_date}")

        events = []

        with sync_playwright() as p:
            # Launch browser (WebKit works better on Mac than Chromium)
            verbose_log("Launching browser...")
            browser = p.webkit.launch(headless=HEADLESS)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN'
            )
            page = context.new_page()

            try:
                # Navigate to economic calendar page
                url = f'https://cn.investing.com/economic-calendar/'
                verbose_log(f"Navigating to {url}")
                page.goto(url, timeout=30000, wait_until='domcontentloaded')

                # Wait for calendar to load
                verbose_log("Waiting for calendar table...")
                page.wait_for_selector('#economicCalendarData', timeout=15000)

                # Set date filter if available (some sites have date pickers)
                # For investing.com, we'll just get whatever is shown

                # Extract event rows
                verbose_log("Extracting event data...")
                current_date = None

                rows = page.query_selector_all('#economicCalendarData tr')
                verbose_log(f"Found {len(rows)} rows")

                for row in rows:
                    try:
                        row_id = row.get_attribute('id')

                        # Check if this is a date row
                        if not row_id:
                            date_cells = row.query_selector_all('td')
                            if date_cells:
                                first_cell = date_cells[0]
                                cell_id = first_cell.get_attribute('id')
                                if cell_id and 'theDay' in cell_id:
                                    # Extract date from timestamp
                                    day_id = cell_id.replace('theDay', '')
                                    if day_id:
                                        try:
                                            timestamp = int(day_id)
                                            current_date = datetime.fromtimestamp(timestamp, tz=pytz.UTC).strftime("%d/%m/%Y")
                                            verbose_log(f"Found date: {current_date}")
                                        except:
                                            pass
                            continue

                        # Check if this is an event row
                        if 'eventRowId_' in row_id and current_date:
                            event = parse_event_row_browser(row, current_date)
                            if event:
                                events.append(event)
                                verbose_log(f"Parsed event: {event['event']} at {event['time']}")

                    except Exception as e:
                        verbose_log(f"Error parsing row: {str(e)[:50]}")
                        continue

                log(f"✓ Fetched {len(events)} events")
                fetch_count += 1

            except PlaywrightTimeout as e:
                log(f"Timeout loading page: {e}", "ERROR")
            except Exception as e:
                log(f"Error during scraping: {str(e)[:100]}", "ERROR")
            finally:
                browser.close()

        return events

    except Exception as e:
        log(f"Browser automation failed: {str(e)[:100]}", "ERROR")
        return []

def parse_event_row_browser(row, current_date: str) -> Optional[Dict]:
    """Parse a single event row from browser"""
    try:
        event = {
            'date': current_date,
            'time': None,
            'zone': None,
            'currency': None,
            'event': None,
            'importance': None,
            'actual': None,
            'forecast': None,
            'previous': None,
        }

        row_id = row.get_attribute('id').replace('eventRowId_', '')
        cells = row.query_selector_all('td')

        for cell in cells:
            cell_class = cell.get_attribute('class') or ''
            cell_id = cell.get_attribute('id') or ''

            # Time
            if 'first left' in cell_class and 'time' in cell_class:
                time_text = cell.inner_text().strip()
                if time_text and time_text.lower() != 'all day':
                    event['time'] = time_text

            # Currency and Zone
            elif 'flagCur' in cell_class:
                title_spans = cell.query_selector_all('span[title]')
                if title_spans:
                    event['zone'] = title_spans[0].get_attribute('title').lower()
                event['currency'] = cell.inner_text().strip()

            # Importance
            elif 'sentiment' in cell_class:
                data_img_key = cell.get_attribute('data-img_key')
                if data_img_key:
                    event['importance'] = IMPORTANCE_MAP.get(data_img_key, None)

            # Event name
            elif cell_class == 'left event':
                event_text = cell.inner_text().strip()
                if '(' in event_text:
                    event_text = event_text.split('(')[0].strip()
                event['event'] = event_text

            # Actual value
            elif cell_id == f'eventActual_{row_id}':
                actual_text = cell.inner_text().strip()
                event['actual'] = actual_text if actual_text != '–' else None

            # Forecast value
            elif cell_id == f'eventForecast_{row_id}':
                forecast_text = cell.inner_text().strip()
                event['forecast'] = forecast_text if forecast_text != '–' else None

            # Previous value
            elif cell_id == f'eventPrevious_{row_id}':
                previous_text = cell.inner_text().strip()
                event['previous'] = previous_text if previous_text != '–' else None

        if event['event']:
            return event
        return None

    except Exception as e:
        verbose_log(f"Error parsing event row: {str(e)[:50]}")
        return None

# ============================================================================
# Database Operations
# ============================================================================

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT,
            zone TEXT,
            currency TEXT,
            event TEXT NOT NULL,
            importance TEXT,
            actual TEXT,
            forecast TEXT,
            previous TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(date, time, zone, event)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON events(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_importance ON events(importance)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_currency ON events(currency)")

    conn.commit()
    conn.close()
    log(f"✓ Database initialized: {DB_PATH}")

def write_to_database(events: List[Dict]) -> int:
    """Write events to database with upsert"""
    global db_write_count

    if not events:
        return 0

    # Filter: Only high-importance US events
    filtered_events = [
        event for event in events
        if event.get('importance') == '高' and event.get('zone') == '美国'
    ]

    if not filtered_events:
        verbose_log("No events match filter criteria (importance='高' and zone='美国')")
        return 0

    log(f"Filtered {len(filtered_events)} events (from {len(events)} total) - importance='高', zone='美国'")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    success_count = 0

    for event in filtered_events:
        try:
            normalized = normalize_event_for_db(event)
            cursor.execute("""
                INSERT INTO events
                (date, time, zone, currency, event, importance,
                 actual, forecast, previous, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, time, zone, event) DO UPDATE SET
                    actual = excluded.actual,
                    forecast = excluded.forecast,
                    previous = excluded.previous,
                    importance = excluded.importance,
                    updated_at = excluded.updated_at
            """, (
                normalized.get('date'),
                normalized.get('time'),
                normalized.get('zone'),
                normalized.get('currency'),
                normalized.get('event'),
                normalized.get('importance'),
                normalized.get('actual'),
                normalized.get('forecast'),
                normalized.get('previous'),
                now,
                now
            ))
            success_count += 1
        except Exception as e:
            verbose_log(f"Database write error: {str(e)[:50]}")

    conn.commit()
    conn.close()
    db_write_count += 1

    return success_count

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

    events = fetch_calendar_with_browser(DAYS_AHEAD)

    if events:
        saved = write_to_database(events)
        log(f"✓ Saved {saved} events to database")
        log(f"📊 Total fetches: {fetch_count}, DB writes: {db_write_count}")
    else:
        log("⚠ No events fetched", "WARN")

    return len(events)

def main():
    """Main entry point"""
    log("=" * 70)
    log("Economic Calendar Scraper (Browser Automation)")
    log("=" * 70)
    log(f"Database: {DB_PATH}")
    log(f"Days ahead: {DAYS_AHEAD}")
    log(f"Headless mode: {HEADLESS}")
    if POLL_INTERVAL:
        log(f"Polling interval: {POLL_INTERVAL}s")
    else:
        log("Mode: Single run")
    log("=" * 70)

    # Initialize database
    init_database()

    # Run once or continuously
    if POLL_INTERVAL:
        log("Starting continuous polling mode...")
        while running:
            try:
                update_data()
                if running:
                    log(f"Sleeping for {POLL_INTERVAL}s...")
                    time.sleep(POLL_INTERVAL)
            except Exception as e:
                log(f"Error in main loop: {str(e)[:100]}", "ERROR")
                if running:
                    time.sleep(60)  # Wait a minute before retrying
    else:
        # Single run
        update_data()
        log("✓ Single run complete")

    log("Program exited")

if __name__ == "__main__":
    main()
