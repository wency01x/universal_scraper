# extractors/base.py
from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright

class BaseExtractor(ABC):
    def __init__(self, url):
        self.url = url

    def fetch_html(self):
        """Boot up a headless browser, render JS, and return the final HTML"""
        
        # Start the Playwright context
        with sync_playwright() as p:
            # Launch Chromium in the background (headless=True means invisible)
            browser = p.chromium.launch(headless=True)
            
            # Create a new tab with a normal-looking User Agent
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Go to the URL and wait until the network is quiet (JS is done executing)
            print(f"[Playwright] Navigating to {self.url}...")
            page.goto(self.url, wait_until="networkidle")
            
            # Extract the fully rendered DOM/HTML
            html = page.content()
            
            # Close the browser to free up RAM
            browser.close()
            
            return html

    @abstractmethod
    def extract(self, html):
        """Specific scrapers will still implement this"""
        pass

    def run(self):
        """The main entry point"""
        html = self.fetch_html()
        return self.extract(html)