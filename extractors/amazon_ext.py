# extractors/amazon_ext.py
from .base import BaseExtractor
from bs4 import BeautifulSoup
import re

class AmazonExtractor(BaseExtractor):
    def extract(self, html):
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Get Title (scoped to centerCol for accuracy)
        center_col = soup.find("div", id="centerCol")
        search_area = center_col if center_col else soup

        title_el = search_area.find("span", id="productTitle")
        title = title_el.get_text(strip=True) if title_el else "Blocked/Not Found"

        # 2. Get Price — search the ENTIRE page, not just centerCol
        #    The price lives in the right-column buybox, NOT in centerCol.
        raw_price = "Price Not Found"
        
        # Strategy A: Hidden input field (most reliable, never empty)
        hidden_price = soup.find("input", id="twister-plus-price-data-price")
        hidden_unit = soup.find("input", id="twister-plus-price-data-price-unit")
        if hidden_price and hidden_price.get("value"):
            symbol = hidden_unit.get("value", "$") if hidden_unit else "$"
            raw_price = f"{symbol}{hidden_price['value']}"
            print(f"[AmazonExtractor] Strategy A (hidden input): {raw_price}")
        else:
            # Strategy B: CSS selector priority list on the full page
            price_selectors = [
                "#buybox .apex-pricetopay-value .a-offscreen",              # Buybox accordion price
                "#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen",  # Core price display
                "#corePrice_desktop .a-offscreen",                          # Classic core price
                "#tp_price_block_total_price_ww .a-offscreen",              # Twister price block
                "#price_inside_buybox",                                     # Inside Buy Box
                "#priceblock_ourprice",                                     # Classic layout
                "#priceblock_dealprice",                                    # Deal price
                "#kindle-price",                                            # Digital/Books
            ]

            for selector in price_selectors:
                found = soup.select_one(selector)
                if found:
                    text = found.get_text(strip=True)
                    if text and text != "":  # Skip empty/whitespace-only matches
                        raw_price = text
                        print(f"[AmazonExtractor] Strategy B matched: {selector} → {raw_price}")
                        break
        
        # 3. DATA CLEANING
        price_digits = re.findall(r"\d[\d,]*\.?\d*", raw_price)
        
        if price_digits:
            clean_price = price_digits[0].replace(",", "")
            status = "Success"
        else:
            clean_price = "N/A"
            status = "Unavailable/Regional Block"

        # 4. Detect currency
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