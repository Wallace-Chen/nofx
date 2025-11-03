#!/usr/bin/env python3
"""
Debug script to inspect CoinGecko trending page HTML structure
"""

import time
from playwright.sync_api import sync_playwright

COINGECKO_URL = 'https://www.coingecko.com/en/highlights/trending-crypto'

with sync_playwright() as p:
    print("Launching browser...")
    browser = p.webkit.launch(headless=False)  # visible browser
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()

    print(f"Navigating to {COINGECKO_URL}")
    page.goto(COINGECKO_URL, timeout=30000, wait_until='domcontentloaded')

    print("Waiting for content...")
    time.sleep(3)

    print("Scrolling...")
    for i in range(5):
        page.evaluate("window.scrollBy(0, 1500)")
        time.sleep(1.5)

    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(2)

    print("\n" + "="*80)
    print("ANALYZING TABLE STRUCTURE")
    print("="*80)

    # Find all table rows
    rows = page.query_selector_all('table tbody tr')
    print(f"\nFound {len(rows)} table rows\n")

    # Analyze first 3 rows in detail
    for idx, row in enumerate(rows[:3]):
        print(f"\n{'='*80}")
        print(f"ROW {idx + 1}")
        print(f"{'='*80}")

        # Get all cells
        cells = row.query_selector_all('td')
        print(f"Number of cells: {len(cells)}")

        for cell_idx, cell in enumerate(cells):
            cell_text = cell.inner_text().strip()
            cell_html = cell.inner_html()[:200]  # First 200 chars

            print(f"\n--- Cell {cell_idx + 1} ---")
            print(f"Text: {cell_text[:100]}")
            print(f"HTML snippet: {cell_html}")

            # Check for data attributes
            attributes = cell.evaluate("""
                (element) => {
                    const attrs = {};
                    for (let attr of element.attributes) {
                        if (attr.name.startsWith('data-')) {
                            attrs[attr.name] = attr.value;
                        }
                    }
                    return attrs;
                }
            """)
            if attributes:
                print(f"Data attributes: {attributes}")

        # Get full row text
        print(f"\n--- Full Row Text ---")
        print(row.inner_text())
        print("\n")

    print("\n" + "="*80)
    print("LOOKING FOR MARKET CAP PATTERNS")
    print("="*80)

    # Search for elements containing dollar amounts with B/M
    import re
    html_content = page.content()

    # Find all $ amounts
    dollar_patterns = re.findall(r'\$[\d,\.]+[BMK]', html_content[:50000])
    print(f"\nFound {len(dollar_patterns)} dollar amounts in HTML:")
    for pattern in set(dollar_patterns[:20]):
        print(f"  {pattern}")

    print("\n\nPress Enter to close browser...")
    input()

    browser.close()
