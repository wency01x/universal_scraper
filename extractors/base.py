# extractors/base.py
from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright


class BaseExtractor(ABC):
    def __init__(self, url):
        self.url = url

    def fetch_html(self):
        """Use Playwright to fetch the fully rendered HTML from the target URL."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # 1. Create context with US-centric settings AND pre-loaded cookies
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )

            # 2. Inject Amazon US-session cookies BEFORE any navigation
            context.add_cookies([
                {
                    "name": "i18n-prefs",
                    "value": "USD",
                    "domain": ".amazon.com",
                    "path": "/"
                },
                {
                    "name": "lc-main",
                    "value": "en_US",
                    "domain": ".amazon.com",
                    "path": "/"
                },
            ])

            page = context.new_page()

            # 3. PHASE 1: Go to Amazon homepage and spoof US ZIP code
            #    This is the nuclear option — cookies alone can't beat server-side Geo-IP.
            #    We must use Amazon's own "Deliver to" modal to set a US address.
            print("[Playwright] Phase 1: Setting US delivery address via ZIP code modal...")
            try:
                page.goto("https://www.amazon.com", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # Click the "Deliver to" button to open the address modal
                deliver_to = page.locator("#nav-global-location-popover-link")
                if deliver_to.is_visible():
                    deliver_to.click()
                    page.wait_for_timeout(1500)

                    # Type the US ZIP code into the modal's input field
                    zip_input = page.locator("#GLUXZipUpdateInput")
                    if zip_input.is_visible():
                        zip_input.fill("10001")  # New York, NY
                        page.wait_for_timeout(500)

                        # Click the "Apply" button
                        apply_btn = page.locator("#GLUXZipUpdate input[type='submit'], #GLUXZipUpdate .a-button-input")
                        if apply_btn.count() > 0:
                            apply_btn.first.click()
                        else:
                            # Fallback: press Enter on the input
                            zip_input.press("Enter")

                        page.wait_for_timeout(2000)

                        # Close the confirmation modal if it appears
                        done_btn = page.locator(".a-popover-footer .a-button-primary, #GLUXConfirmClose, .a-button-close")
                        if done_btn.count() > 0:
                            done_btn.first.click()
                            page.wait_for_timeout(1000)

                    print("[Playwright] ✓ US ZIP code 10001 set successfully")
                else:
                    print("[Playwright] ⚠ Could not find 'Deliver to' button, proceeding anyway...")

            except Exception as e:
                print(f"[Playwright] ⚠ ZIP code spoofing warning (non-fatal): {e}")

            # 4. PHASE 2: Navigate to the actual product page
            print(f"[Playwright] Phase 2: Navigating to product: {self.url}")
            try:
                page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"[Playwright] Navigation warning (non-fatal): {e}")

            # 5. Wait for the page content to settle (dynamic pricing scripts)
            page.wait_for_timeout(5000)

            # 6. Save debug HTML for troubleshooting
            html = page.content()
            try:
                with open("debug_amazon.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("[Playwright] Debug HTML saved to debug_amazon.html")
            except Exception:
                pass

            browser.close()
            return html

    @abstractmethod
    def extract(self, html):
        """Parse the HTML and return a dictionary of extracted data."""
        pass

    def run(self):
        """Main entry point: fetch HTML, then extract data from it."""
        print(f"[{self.__class__.__name__}] Fetching HTML from: {self.url}")
        html = self.fetch_html()
        print(f"[{self.__class__.__name__}] Extracting data...")
        data = self.extract(html)
        print(f"[{self.__class__.__name__}] Done.")
        return data