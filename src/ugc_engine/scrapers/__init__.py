"""Signal sources. Each scraper returns a list of dicts with:
platform, niche, title, snippet, source_url, brand_domain, dedupe_key, signal_type ('post' | 'ads')."""
from .ads import scrape_ads
from .xray import scrape_xray

__all__ = ["scrape_ads", "scrape_xray"]
