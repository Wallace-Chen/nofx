#!/usr/bin/env python3
"""
Quick test to verify setup is correct
"""

import sys

def test_imports():
    """Test if all required packages are installed"""
    print("Testing imports...")

    try:
        import playwright
        print("✓ playwright installed")
    except ImportError:
        print("❌ playwright not installed")
        print("   Run: pip install playwright")
        return False

    try:
        import pytz
        print("✓ pytz installed")
    except ImportError:
        print("❌ pytz not installed")
        print("   Run: pip install pytz")
        return False

    try:
        from dotenv import load_dotenv
        print("✓ python-dotenv installed")
    except ImportError:
        print("❌ python-dotenv not installed")
        print("   Run: pip install python-dotenv")
        return False

    return True

def test_browser():
    """Test if browser is installed"""
    print("\nTesting browser setup...")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                print("✓ Chromium browser installed and working")
                browser.close()
                return True
            except Exception as e:
                print(f"❌ Browser launch failed: {e}")
                print("   Run: playwright install chromium")
                return False
    except Exception as e:
        print(f"❌ Playwright error: {e}")
        return False

def test_database():
    """Test database functionality"""
    print("\nTesting database...")

    try:
        import sqlite3
        import os

        test_db = "test_calendar.db"

        # Create test database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_events (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)

        cursor.execute("INSERT INTO test_events (name) VALUES (?)", ("test",))
        conn.commit()

        cursor.execute("SELECT * FROM test_events")
        result = cursor.fetchone()

        conn.close()

        # Clean up
        os.remove(test_db)

        if result:
            print("✓ Database operations working")
            return True
        else:
            print("❌ Database query failed")
            return False

    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Economic Calendar Scraper - Setup Test")
    print("=" * 60)
    print()

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Browser", test_browser()))
    results.append(("Database", test_database()))

    print()
    print("=" * 60)
    print("Test Results:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{name:20} {status}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("🎉 All tests passed! You're ready to run the scraper.")
        print()
        print("Try running:")
        print("  python3 calendar_scraper.py")
        return 0
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
