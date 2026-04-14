# extractors/amazon_ext.py
from .base_hybrid import HybridBaseExtractor # <-- Uses the heavy-duty login engine

class AmazonExtractor(HybridBaseExtractor):
    def extract(self, html):
        # 5 lines of code to find the <span class="a-price-whole">
        pass