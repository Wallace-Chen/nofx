#!/usr/bin/env python3
"""
Crypto News Scraper with Browser Automation
Fetches news from TheBlockBeats and saves to SQLite database

Features:
- ✅ Browser automation to fetch crypto news
- ✅ Save to SQLite with title, content, timestamp, importance
- ✅ Duplicate detection (avoid re-saving same news)
- ✅ Database size management (delete old news when > 1 MB)
- ✅ Continuous polling support
- ✅ Pagination/scroll support (fetch up to 20 news)

Dependencies:
    pip install playwright
    playwright install webkit  # Use webkit on Mac

Usage:
    # Default run (fetch once)
    python3 news_scraper.py

    # Continuous polling (5 minute interval)
    python3 news_scraper.py --interval 300

    # Debug mode (visible browser)
    python3 news_scraper.py --headless false --verbose
"""

import os
import sys
import time
import sqlite3
import signal
import argparse
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo

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

parser = argparse.ArgumentParser(description='Crypto News Scraper')
parser.add_argument('--interval', type=int, default=None, help='Polling interval in seconds (default: one-time run)')
parser.add_argument('--headless', type=str, default='true', help='Run browser in headless mode (default: true)')
parser.add_argument('--verbose', action='store_true', help='Verbose logging')
parser.add_argument('--db', type=str, default='news.db', help='Database file path (default: news.db)')
parser.add_argument('--max-news', type=int, default=40, help='Maximum news to fetch per run (default: 40)')
args = parser.parse_args()

# Configuration
DB_PATH = args.db
HEADLESS = args.headless.lower() in ('true', '1', 'yes')
VERBOSE = args.verbose
POLL_INTERVAL = args.interval
MAX_NEWS_COUNT = args.max_news
MAX_DB_SIZE = 1 * 1024 * 1024  # 1 MB
NEWS_URL = 'https://www.theblockbeats.info/newsflash'

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
# Database Operations
# ============================================================================

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            timestamp TEXT NOT NULL,
            importance TEXT,
            hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON news(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON news(hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON news(created_at)")

    conn.commit()
    conn.close()
    log(f"✓ Database initialized: {DB_PATH}")

def get_db_size() -> int:
    """Get database file size in bytes"""
    if os.path.exists(DB_PATH):
        return os.path.getsize(DB_PATH)
    return 0

def cleanup_old_news():
    """Delete old news when database exceeds size limit"""
    db_size = get_db_size()
    if db_size <= MAX_DB_SIZE:
        return

    log(f"⚠️  Database size {db_size/1024:.1f} KB exceeds limit {MAX_DB_SIZE/1024:.1f} KB")
    log("Cleaning up old news...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Count total news
    cursor.execute("SELECT COUNT(*) FROM news")
    total_count = cursor.fetchone()[0]

    # Delete oldest 30% of news
    delete_count = int(total_count * 0.3)
    if delete_count > 0:
        cursor.execute("""
            DELETE FROM news
            WHERE id IN (
                SELECT id FROM news
                ORDER BY created_at ASC
                LIMIT ?
            )
        """, (delete_count,))

        conn.commit()
        log(f"✓ Deleted {delete_count} old news items ({delete_count}/{total_count})")

        # Vacuum to reclaim space
        cursor.execute("VACUUM")
        log(f"✓ Database size after cleanup: {get_db_size()/1024:.1f} KB")

    conn.close()

def compute_news_hash(title: str, content: str) -> str:
    """Compute hash for duplicate detection"""
    # Use title + first 100 chars of content for hash
    content_snippet = content[:100] if content else ""
    hash_input = f"{title}|{content_snippet}"
    return hashlib.md5(hash_input.encode('utf-8')).hexdigest()

def save_news(news_list: List[Dict]) -> int:
    """Save news to database with duplicate detection"""
    if not news_list:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    saved_count = 0
    duplicate_count = 0

    for news in news_list:
        try:
            title = news.get('title', '').strip()
            content = news.get('content', '').strip()
            timestamp = news.get('timestamp', '')
            importance = news.get('importance', 'medium')

            if not title:
                verbose_log("Skipping news with empty title")
                continue

            # Compute hash for duplicate detection
            news_hash = compute_news_hash(title, content)

            # Try to insert (will fail if hash exists due to UNIQUE constraint)
            cursor.execute("""
                INSERT INTO news (title, content, timestamp, importance, hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, content, timestamp, importance, news_hash, now))

            saved_count += 1
            verbose_log(f"Saved: {title[:50]}...")

        except sqlite3.IntegrityError:
            # Duplicate news (hash already exists)
            duplicate_count += 1
            verbose_log(f"Duplicate skipped: {title[:50]}...")
        except Exception as e:
            log(f"Error saving news: {str(e)[:100]}", "ERROR")

    conn.commit()
    conn.close()

    if duplicate_count > 0:
        log(f"✓ Saved {saved_count} new items, skipped {duplicate_count} duplicates")
    else:
        log(f"✓ Saved {saved_count} news items to database")

    return saved_count

# ============================================================================
# Browser Automation
# ============================================================================

def normalize_title(title: str) -> str:
    """Normalize title for better duplicate detection"""
    import re
    # Remove leading timestamps (HH:MM pattern)
    title = re.sub(r'^\d{1,2}:\d{2}\s+', '', title)
    # Remove extra whitespace
    title = ' '.join(title.split())
    # Convert to lowercase for comparison
    return title.lower().strip()

def extract_importance(news_element) -> str:
    """Extract importance level from news element"""
    # Try to find importance indicators (badges, colors, etc.)
    # Default to 'medium' if not found
    try:
        # Look for badge or tag elements
        badge = news_element.query_selector('.badge, .tag, .label, [class*="importance"]')
        if badge:
            text = badge.inner_text().lower()
            if '重要' in text or 'important' in text or 'high' in text:
                return 'high'
            elif '紧急' in text or 'urgent' in text or 'critical' in text:
                return 'critical'
            elif '低' in text or 'low' in text:
                return 'low'

        # Check for visual indicators (red color, etc.)
        style = news_element.get_attribute('style') or ''
        class_name = news_element.get_attribute('class') or ''

        if 'red' in style or 'red' in class_name or 'urgent' in class_name:
            return 'high'

    except Exception:
        pass

    return 'medium'

def fetch_news() -> List[Dict]:
    """Fetch news using browser automation"""
    global fetch_count

    try:
        log(f"Fetching news from {NEWS_URL}...")
        news_list = []

        with sync_playwright() as p:
            # Launch browser (WebKit works better on Mac)
            verbose_log("Launching browser...")
            browser = p.webkit.launch(headless=HEADLESS)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN'
            )
            page = context.new_page()

            try:
                # Navigate to news page
                verbose_log(f"Navigating to {NEWS_URL}")
                page.goto(NEWS_URL, timeout=30000, wait_until='domcontentloaded')

                # Wait for news content to load
                verbose_log("Waiting for news content...")
                time.sleep(3)

                # Scroll down to load more content (3 times)
                verbose_log("Scrolling to load more news...")
                for i in range(3):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(1.5)

                # Try to click "load more" button if exists
                try:
                    load_more_selectors = [
                        'button:has-text("加载更多")',
                        'button:has-text("Load More")',
                        'a:has-text("更多")',
                        '.load-more',
                        '[class*="loadmore"]',
                        '[class*="load-more"]'
                    ]

                    for selector in load_more_selectors:
                        try:
                            load_more = page.query_selector(selector)
                            if load_more and load_more.is_visible():
                                verbose_log(f"Clicking load more button: {selector}")
                                load_more.click()
                                time.sleep(2)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    verbose_log(f"No load more button found: {str(e)[:50]}")

                # Extract news items
                verbose_log("Extracting news items...")

                # Use specific selector for TheBlockBeats news wrapper
                news_elements = page.query_selector_all('.news-flash-wrapper')

                verbose_log(f"Found {len(news_elements)} news containers")

                # Track seen titles to avoid duplicates during extraction
                seen_titles = set()
                extracted_count = 0

                # Extract news data (limit to MAX_NEWS_COUNT unique items)
                for i, element in enumerate(news_elements):
                    # Stop if we've extracted enough unique news
                    if extracted_count >= MAX_NEWS_COUNT:
                        break

                    try:
                        # Extract title from specific TheBlockBeats structure
                        # Try .news-flash-title-text first (the actual title div)
                        title_elem = element.query_selector('.news-flash-title-text')
                        if title_elem:
                            title = title_elem.inner_text().strip()
                        else:
                            # Fallback: try the <a> tag's title attribute
                            link_elem = element.query_selector('a.news-flash-title')
                            if link_elem:
                                title = link_elem.get_attribute('title')
                                if not title:
                                    # If no title attribute, get text content
                                    title_text = link_elem.inner_text().strip()
                                    # Remove timestamp (first line)
                                    lines = title_text.split('\n')
                                    title = lines[1] if len(lines) > 1 else lines[0]
                            else:
                                title = None

                        if not title or len(title) < 5:
                            verbose_log(f"Skipping item {i+1} - no valid title")
                            continue

                        # Skip if title is too long (likely content mistaken as title)
                        if len(title) > 150:
                            verbose_log(f"Skipping item {i+1} - title too long: {title[:50]}...")
                            continue

                        # Normalize title for duplicate detection
                        normalized_title = normalize_title(title)

                        # Check for duplicate title (using normalized version)
                        if normalized_title in seen_titles:
                            verbose_log(f"Skipping item {i+1} - duplicate title: {title[:50]}...")
                            continue

                        # Mark normalized title as seen
                        seen_titles.add(normalized_title)

                        # Extract content - get all text from wrapper, then remove title
                        full_text = element.inner_text().strip()
                        lines = full_text.split('\n')

                        # First line is usually timestamp + title, rest is content
                        # Join all lines except the first one (which has timestamp + title)
                        if len(lines) > 1:
                            content = '\n'.join(lines[1:]).strip()
                        else:
                            content = ""

                        # Extract timestamp from the <a> tag text
                        # Format is "HH:MM Title" on the same line
                        # Original time is Beijing time (UTC+8), convert to Texas time (US/Central)
                        link_elem = element.query_selector('a.news-flash-title')
                        timestamp = ""
                        if link_elem:
                            link_text = link_elem.inner_text().strip()
                            # Extract HH:MM pattern from the beginning
                            import re
                            time_match = re.match(r'^(\d{1,2}:\d{2})\s', link_text)
                            if time_match:
                                time_str = time_match.group(1)
                                # Parse as Beijing time
                                beijing_tz = ZoneInfo("Asia/Shanghai")
                                texas_tz = ZoneInfo("America/Chicago")

                                # Get current time in Beijing timezone
                                beijing_now = datetime.now(beijing_tz)

                                # Parse the time (HH:MM)
                                hour, minute = map(int, time_str.split(':'))

                                # Create datetime for today with this time
                                beijing_time = beijing_now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                                # If the news time is in the future, it must be from yesterday
                                if beijing_time > beijing_now:
                                    beijing_time = beijing_time - timedelta(days=1)

                                # Convert to Texas time
                                texas_time = beijing_time.astimezone(texas_tz)
                                timestamp = texas_time.strftime("%Y-%m-%d %H:%M:%S")

                        # If no timestamp found, use current time (Beijing -> Texas)
                        if not timestamp:
                            beijing_tz = ZoneInfo("Asia/Shanghai")
                            texas_tz = ZoneInfo("America/Chicago")
                            beijing_now = datetime.now(beijing_tz)
                            texas_now = beijing_now.astimezone(texas_tz)
                            timestamp = texas_now.strftime("%Y-%m-%d %H:%M:%S")

                        # Extract importance
                        importance = extract_importance(element)

                        news_item = {
                            'title': title,
                            'content': content[:1000],  # Limit content length
                            'timestamp': timestamp,
                            'importance': importance
                        }

                        news_list.append(news_item)
                        extracted_count += 1
                        verbose_log(f"Extracted #{extracted_count}: {title[:50]}... ({importance})")

                    except Exception as e:
                        verbose_log(f"Error extracting news item {i+1}: {str(e)[:50]}")
                        continue

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
        log(f"✓ Fetched {len(news_list)} news items")
        return news_list

    except Exception as e:
        log(f"Fatal error: {str(e)}", "ERROR")
        return []

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
    """Fetch and update news data"""
    log("=" * 70)
    log("Starting news collection...")

    # Check database size and cleanup if needed
    cleanup_old_news()

    news_list = fetch_news()

    if news_list:
        saved = save_news(news_list)
        log(f"📊 Total fetches: {fetch_count}, DB size: {get_db_size()/1024:.1f} KB")
    else:
        log("⚠ No news fetched", "WARN")

    return len(news_list)

def main():
    """Main entry point"""
    log("=" * 70)
    log("Crypto News Scraper")
    log("=" * 70)
    log(f"Database: {DB_PATH}")
    log(f"Max news per run: {MAX_NEWS_COUNT}")
    log(f"Headless mode: {HEADLESS}")

    if POLL_INTERVAL:
        log(f"Polling interval: {POLL_INTERVAL}s")
    else:
        log(f"Mode: Single run")

    log("=" * 70)

    # Initialize database
    init_database()

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
