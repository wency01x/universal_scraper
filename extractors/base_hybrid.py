from playwright.sync_api import sync_playwright
import httpx

class HybridExtractor:
    def __init__(self, target_url):
        self.target_url = target_url
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        self.headers = {"User-Agent": self.user_agent}

    def get_auth_cookies(self):
        """Step 1: Use Playwright just to log in and steal the cookies"""
        print("[Playwright] Booting to bypass login...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # We use a 'context' in Playwright to store the session data
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()
            
            # Go to the login page and fill it out
            page.goto("https://example.com/login")
            page.fill("input[name='username']", "my_user")
            page.fill("input[name='password']", "my_password")
            page.click("button[type='submit']")
            
            # Wait for the login to actually finish loading
            page.wait_for_url("**/dashboard") 
            
            # STEAL THE COOKIES!
            raw_cookies = context.cookies()
            browser.close()

            # Format them so HTTPX can understand them
            httpx_cookies = {cookie["name"]: cookie["value"] for cookie in raw_cookies}
            return httpx_cookies

    def fetch_fast_data(self, auth_cookies):
        """Step 2: Use HTTPX to scrape the data at lightning speed"""
        print("[HTTPX] Fetching data with stolen cookies...")
        
        # We pass the formatted cookies directly into the fast client
        with httpx.Client(headers=self.headers, cookies=auth_cookies) as client:
            response = client.get(self.target_url)
            response.raise_for_status()
            return response.text