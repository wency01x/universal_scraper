# extractors/base.py
from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright


class BaseExtractor(ABC):
    def __init__(self, url):
        self.url = url

    def fetch_html(self):
        """
        Use Playwright to fetch the fully rendered HTML from the target URL.
        Also attempts to extract price directly from the live DOM via XPath
        before saving the HTML — this is used as the PRIMARY price source.
        """
        self._live_price = None  # Will be set if Playwright XPath finds a price

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
            print("[Playwright] Phase 1: Setting US delivery address via ZIP code modal...")
            try:
                page.goto("https://www.amazon.com", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                deliver_to = page.locator("#nav-global-location-popover-link")
                if deliver_to.is_visible():
                    deliver_to.click()
                    page.wait_for_timeout(1500)

                    zip_input = page.locator("#GLUXZipUpdateInput")
                    if zip_input.is_visible():
                        zip_input.fill("10001")
                        page.wait_for_timeout(500)

                        apply_btn = page.locator("#GLUXZipUpdate input[type='submit'], #GLUXZipUpdate .a-button-input")
                        if apply_btn.count() > 0:
                            apply_btn.first.click()
                        else:
                            zip_input.press("Enter")

                        page.wait_for_timeout(2000)

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

            # 5. Wait for the page content to settle
            page.wait_for_timeout(5000)

            # ══════════════════════════════════════════════════════════════
            # 6. PHASE 3: Live-DOM XPath extraction (PRIMARY price source)
            #    Extract the price directly from the rendered page using
            #    Playwright's XPath locators — this sees JavaScript-rendered
            #    content that may not appear in the static HTML.
            # ══════════════════════════════════════════════════════════════
            print("[Playwright] Phase 3: Attempting live-DOM XPath price extraction...")
            self._live_price = self._extract_price_xpath(page)

            # 7. Save the full HTML for fallback parsing
            html = page.content()
            try:
                with open("debug_amazon.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("[Playwright] Debug HTML saved to debug_amazon.html")
            except Exception:
                pass

            browser.close()
            return html

    def _extract_price_xpath(self, page):
        """
        Use Playwright XPath locators to extract price from the LIVE rendered page.
        This is the most reliable method because it operates on the actual DOM
        after JavaScript has executed.
        
        Returns a price string (e.g. "$49.99") or None if not found.
        """
        # XPath priority list — ordered from most reliable to least
        xpath_strategies = [
            # Strategy 1: Hidden input (Amazon-owned products with Buy Box)
            ("hidden_input",
             "//input[@id='twister-plus-price-data-price']",
             "value"),  # Extract from 'value' attribute

            # Strategy 2: Accessibility label with the full price
            ("accessibility_label",
             "//span[contains(@class, 'apex-pricetopay-accessibility-label')]",
             "text"),

            # Strategy 3: Core price display's priceToPay (Buy Box)
            ("buybox_priceToPay",
             "//div[@id='corePrice_desktop']//span[contains(@class, 'priceToPay')]//span[@class='a-offscreen' and string-length(normalize-space()) > 1]",
             "text"),

            # Strategy 4: corePriceDisplay feature div
            ("corePriceDisplay",
             "//div[@id='corePriceDisplay_desktop_feature_div']//span[contains(@class, 'priceToPay')]//span[@class='a-offscreen' and string-length(normalize-space()) > 1]",
             "text"),

            # Strategy 5: New Buy Box price
            ("newBuyBox",
             "//span[@id='newBuyBoxPrice']//span[@class='a-offscreen' and string-length(normalize-space()) > 1]",
             "text"),

            # Strategy 6: Classic layout price IDs
            ("priceblock_ourprice",
             "//span[@id='priceblock_ourprice']",
             "text"),
            ("priceblock_dealprice",
             "//span[@id='priceblock_dealprice']",
             "text"),
            ("price_inside_buybox",
             "//span[@id='price_inside_buybox']",
             "text"),

            # Strategy 7: OLP "X options from $Y.YY" (third-party only listings)
            ("olp_message",
             "//span[contains(@class, 'olp-message') or contains(@class, 'olpWrapper')]",
             "text"),

            # Strategy 8: Twister swatch price for the SELECTED variant
            ("twister_selected_price",
             "//li[@data-initiallyselected='true']//span[contains(@class, 'a-offscreen') and string-length(normalize-space()) > 1]",
             "text"),

            # Strategy 9: Any visible price in the main price area
            ("apex_price_aria",
             "//div[contains(@class, 'apex_on_twister_price')]//span[contains(@class, 'apex-pricetopay-accessibility-label')]",
             "text"),

            # Strategy 10: Fallback — first visible a-color-price span
            ("color_price_fallback",
             "//span[contains(@class, 'a-color-price') and contains(text(), '$')]",
             "text"),
        ]

        for name, xpath, extract_type in xpath_strategies:
            try:
                locator = page.locator(f"xpath={xpath}")
                if locator.count() > 0:
                    if extract_type == "value":
                        # Get the value attribute (for hidden inputs)
                        val = locator.first.get_attribute("value")
                        if val and val.strip():
                            price = f"${val.strip()}"
                            print(f"[XPath] ✓ Strategy '{name}': {price}")
                            return price
                    else:
                        # Get text content
                        text = locator.first.text_content()
                        if text and text.strip() and len(text.strip()) > 1:
                            price = text.strip()
                            print(f"[XPath] ✓ Strategy '{name}': {price}")
                            return price
            except Exception as e:
                print(f"[XPath] Strategy '{name}' error: {e}")
                continue

        print("[XPath] ✗ No price found via live-DOM XPath")
        return None

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