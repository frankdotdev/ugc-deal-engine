"""Active advertisers from TikTok / Meta ad libraries (via Apify actors), grouped per advertiser."""
from __future__ import annotations

import json
import logging
import random

from ..config import Settings
from ..enrichment import clean_domain

log = logging.getLogger(__name__)


def _pick(d: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        if d.get(k):
            return str(d[k])
    return ""


def group_ads(items, platform: str, niche: str) -> list[dict]:
    groups: dict[str, dict] = {}
    for ad in items:
        name = _pick(ad, ("advertiser", "advertiserName", "pageName", "page_name", "brand", "name")).strip()
        if not name:
            continue
        g = groups.setdefault(name, {"n": 0, "dest": "", "copy": ""})
        g["n"] += 1
        g["dest"] = g["dest"] or _pick(ad, ("destinationUrl", "linkUrl", "link_url", "landingPage", "website", "ctaUrl"))
        g["copy"] = g["copy"] or _pick(ad, ("caption", "adText", "body", "text", "title"))[:220]
    return [{
        "platform": platform, "niche": niche, "brand_name": name, "signal_type": "ads",
        "title": f"{name} - active {platform} advertiser",
        "snippet": f"{name} has {g['n']} active ad(s) found for '{niche}' on {platform}. Sample copy: {g['copy']}",
        "source_url": g["dest"] or f"{platform}:{name}", "brand_domain": clean_domain(g["dest"]),
        "dedupe_key": f"ad:{platform}:{name.lower()}",
    } for name, g in groups.items()]


def scrape_ads(s: Settings) -> list[dict]:
    if not s.apify_api_token:
        return []
    try:
        from apify_client import ApifyClient
    except ImportError:
        log.warning("apify-client is not installed; skipping ad libraries")
        return []
    client = ApifyClient(s.apify_api_token)
    jobs = []
    if s.apify_actor_tiktok:
        jobs.append(("TikTok Ad Library", s.apify_actor_tiktok, s.apify_input_tiktok))
    if s.apify_actor_meta:
        jobs.append(("Meta Ad Library", s.apify_actor_meta, s.apify_input_meta))
    out: list[dict] = []
    niches = random.sample(list(s.target_niches), min(s.apify_niches_per_run, len(s.target_niches)))
    for platform, actor, template in jobs:
        for niche in niches:
            try:
                run_input = json.loads(template.replace("{niche}", niche.replace('"', "")))
                run = client.actor(actor).call(run_input=run_input, timeout_secs=300)
                out.extend(group_ads(client.dataset(run["defaultDatasetId"]).iterate_items(), platform, niche))
            except Exception as exc:
                log.error("Apify %s / %s failed: %s", platform, niche, exc)
    return out
