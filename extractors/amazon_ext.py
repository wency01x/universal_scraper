# extractors/amazon_ext.py
from .base import BaseExtractor
from lxml import html as lxml_html
import re
import json


class AmazonExtractor(BaseExtractor):
    def extract(self, raw_html):
        """
        Extract product data from Amazon HTML using XPath.
        
        Price extraction priority:
        1. Live-DOM XPath (extracted by Playwright in base.py — most reliable)
        2. lxml XPath on the saved HTML (fallback)
        3. Embedded JSON data parsing (last resort for OLP/third-party pages)
        """
        tree = lxml_html.fromstring(raw_html)

        # ════════════════════════════════════════════════════════════════
        # 1. TITLE — XPath extraction
        # ════════════════════════════════════════════════════════════════
        title_nodes = tree.xpath('//span[@id="productTitle"]/text()')
        title = title_nodes[0].strip() if title_nodes else "Blocked/Not Found"

        # ════════════════════════════════════════════════════════════════
        # 2. PRICE — Priority 1: Live-DOM price from Playwright (base.py)
        # ════════════════════════════════════════════════════════════════
        raw_price = None
        
        if hasattr(self, '_live_price') and self._live_price:
            raw_price = self._live_price
            print(f"[AmazonExtractor] Using live-DOM XPath price: {raw_price}")

        # ════════════════════════════════════════════════════════════════
        # 3. PRICE — Priority 2: lxml XPath on saved HTML (fallback)
        # ════════════════════════════════════════════════════════════════
        if not raw_price:
            xpath_selectors = [
                # Hidden input (Amazon-owned Buy Box)
                ('//input[@id="twister-plus-price-data-price"]/@value',
                 "hidden_input", True),

                # Accessibility label  
                ('//span[contains(@class, "apex-pricetopay-accessibility-label")]/text()',
                 "accessibility_label", False),

                # Core price → priceToPay offscreen
                ('//div[@id="corePrice_desktop"]//span[contains(@class, "priceToPay")]//span[@class="a-offscreen"]/text()',
                 "corePrice_priceToPay", False),

                # corePriceDisplay feature div
                ('//div[@id="corePriceDisplay_desktop_feature_div"]//span[contains(@class, "priceToPay")]//span[@class="a-offscreen"]/text()',
                 "corePriceDisplay", False),

                # New Buy Box
                ('//span[@id="newBuyBoxPrice"]//span[@class="a-offscreen"]/text()',
                 "newBuyBox", False),

                # Classic IDs
                ('//span[@id="priceblock_ourprice"]/text()', "priceblock_ourprice", False),
                ('//span[@id="priceblock_dealprice"]/text()', "priceblock_dealprice", False),
                ('//span[@id="price_inside_buybox"]/text()', "price_inside_buybox", False),

                # OLP "X options from $Y"
                ('//span[contains(@class, "olpWrapper")]/text()',
                 "olp_wrapper", False),

                # Selected twister variant price (aria-hidden visible text)
                ('//li[@data-initiallyselected="true"]//span[@aria-hidden="true" and contains(text(), "$")]/text()',
                 "twister_selected_visible", False),

                # Twister accessibility label price
                ('//div[contains(@class, "apex_on_twister_price")]//span[contains(@class, "apex-pricetopay-accessibility-label")]/text()',
                 "twister_apex_label", False),

                # Any a-color-price with $
                ('//span[contains(@class, "a-color-price") and contains(text(), "$")]/text()',
                 "color_price", False),
            ]

            for xpath, name, is_attr in xpath_selectors:
                try:
                    results = tree.xpath(xpath)
                    for result in results:
                        text = str(result).strip()
                        if text and len(text) > 1:
                            if is_attr:
                                # Hidden input value — prepend $
                                raw_price = f"${text}"
                            else:
                                raw_price = text
                            print(f"[XPath-lxml] ✓ '{name}': {raw_price}")
                            break
                    if raw_price:
                        break
                except Exception as e:
                    print(f"[XPath-lxml] Error in '{name}': {e}")
                    continue

        # ════════════════════════════════════════════════════════════════
        # 4. PRICE — Priority 3: Embedded JSON (OLP/third-party pages)
        # ════════════════════════════════════════════════════════════════
        if not raw_price:
            script_nodes = tree.xpath('//script[@type="a-state"]/text()')
            for script_text in script_nodes:
                if raw_price:
                    break
                try:
                    data = json.loads(script_text)
                    if isinstance(data, dict) and "sortedDimValuesForAllDims" in data:
                        for dim_name, dim_vals in data["sortedDimValuesForAllDims"].items():
                            for dv in dim_vals:
                                if dv.get("dimensionValueState") == "SELECTED":
                                    for slot in dv.get("slots", []):
                                        dd = slot.get("displayData", {})
                                        olp_price = dd.get("priceWithoutCurrencySymbol", "")
                                        if olp_price:
                                            raw_price = f"${olp_price}"
                                            print(f"[XPath-JSON] ✓ twister OLP price: {raw_price}")
                                            break
                                        olp_msg = dd.get("olpMessage", "")
                                        if olp_msg:
                                            m = re.search(r"\$(\d[\d,]*\.?\d*)", olp_msg)
                                            if m:
                                                raw_price = f"${m.group(1)}"
                                                print(f"[XPath-JSON] ✓ twister OLP message: {raw_price}")
                                                break
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue

        # If still nothing, set default
        if not raw_price:
            raw_price = "Price Not Found"

        # ════════════════════════════════════════════════════════════════
        # 5. DATA CLEANING — extract numeric price from raw string
        # ════════════════════════════════════════════════════════════════
        price_digits = re.findall(r"\d[\d,]*\.?\d*", raw_price)

        if price_digits:
            clean_price = price_digits[0].replace(",", "")
            status = "Success"
        else:
            clean_price = "N/A"
            status = "Unavailable/Regional Block"

        # 6. Detect currency from the raw string
        if "PHP" in raw_price or "₱" in raw_price:
            currency = "PHP"
        elif "£" in raw_price:
            currency = "GBP"
        elif "€" in raw_price:
            currency = "EUR"
        else:
            currency = "USD"

        return {
            "title": title,
            "price": clean_price,
            "currency": currency,
            "status": status,
            "debug_raw": raw_price[:50]
        }