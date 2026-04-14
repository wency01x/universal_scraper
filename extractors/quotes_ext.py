# extractors/quotes_ext.py
from .base import BaseExtractor
from bs4 import BeautifulSoup

class QuotesExtractor(BaseExtractor):
    def extract(self, html):
        soup = BeautifulSoup(html, "html.parser")
        quotes = []
        
        for quote_div in soup.find_all("div", class_="quote"):
            text = quote_div.find("span", class_="text").get_text()
            author = quote_div.find("small", class_="author").get_text()
            quotes.append({"quote": text, "author": author})
            
        # THIS IS THE LINE YOU WERE MISSING!
        return {"total_quotes": len(quotes), "data": quotes}