"""Google X-Ray searches (via Serper.dev) for buyers asking for UGC creators."""
from __future__ import annotations

import json
import logging
import time

from ..config import Settings
from ..enrichment import clean_domain
from ..http import session

log = logging.getLogger(__name__)

XRAY_QUERIES = [
    ("X (Twitter)", "DTC / E-Com", 'site:x.com ("looking for" OR "need" OR "hiring") ("UGC creator" OR "UGC creators" OR "TikTok creators") ("email" OR "DM" OR "portfolio")'),
    ("X (Twitter)", "Ad creatives", 'site:x.com ("need" OR "looking for") ("ad creatives" OR "UGC videos" OR "creators for our ads") ("DTC" OR "brand" OR "founder")'),
    ("LinkedIn Posts", "Agency / Brand", 'site:linkedin.com/posts ("looking for UGC" OR "hiring UGC creators" OR "need UGC creators") ("email" OR "DM" OR "portfolio")'),
    ("Google Forms Brief", "Brand Application", 'site:docs.google.com/forms ("UGC" OR "creator application") ("rates" OR "portfolio" OR "TikTok")'),
    ("Notion Brief", "Direct Brief", 'site:notion.site ("UGC brief" OR "creator application" OR "UGC creators")'),
    ("TikTok", "TikTok Shop", 'site:tiktok.com ("looking for ugc creators" OR "paid ugc" OR "ugc creators wanted")'),
    ("Brand Websites", "Creator Programs", '("become a UGC creator" OR "UGC creator application" OR "apply to be a creator") ("paid" OR "per video") -site:reddit.com'),
]


def build_queries(s: Settings) -> list[tuple[str, str, str]]:
    queries = list(XRAY_QUERIES)
    for niche in s.target_niches[:3]:
        queries.append((
            "X (Twitter)", niche,
            f'site:x.com ("UGC" OR "creators") ("need" OR "looking for" OR "hiring") "{niche}"',
        ))
    return queries


def scrape_xray(s: Settings) -> list[dict]:
    if not s.serper_api_key:
        return []
    headers = {"X-API-KEY": s.serper_api_key, "Content-Type": "application/json"}
    out: list[dict] = []
    for platform, niche, query in build_queries(s):
        try:
            r = session().post(
                "https://google.serper.dev/search", headers=headers,
                data=json.dumps({"q": query, "tbs": "qdr:w", "num": 10}), timeout=20,
            )
            if r.status_code != 200:
                log.warning("Serper %s returned HTTP %s", platform, r.status_code)
                continue
            for res in r.json().get("organic", []):
                link = res.get("link", "")
                if link:
                    out.append({
                        "platform": platform, "niche": niche, "title": res.get("title", ""),
                        "snippet": res.get("snippet", ""), "source_url": link,
                        "brand_domain": clean_domain(link), "dedupe_key": link, "signal_type": "post",
                    })
            time.sleep(0.5)
        except Exception as exc:
            log.error("Serper query failed (%s): %s", platform, exc)
    return out
