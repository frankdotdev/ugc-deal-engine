"""Scan -> qualify -> enrich -> store."""
from __future__ import annotations

import logging
import threading

from . import ai, clock, enrichment
from . import repository as repo
from .config import Settings, get_settings
from .scrapers import scrape_ads, scrape_xray

log = logging.getLogger(__name__)
_lock = threading.Lock()


def run_discovery(s: Settings | None = None) -> dict:
    s = s or get_settings()
    if not _lock.acquire(blocking=False):
        return {"busy": True}
    try:
        items = scrape_xray(s) + scrape_ads(s)
        added = 0
        for item in items:
            if repo.lead_exists(item["dedupe_key"]):
                continue
            verdict = ai.qualify(item, s)
            if not verdict or int(verdict.get("intent_score", 0)) < s.min_score_save:
                continue
            domain = item.get("brand_domain") or enrichment.clean_domain(verdict.get("inferred_domain", ""))
            email, contact, first = enrichment.extract_email(item.get("snippet", "")), "", ""
            if email:
                contact = "Contact from post"
            elif domain:
                email, contact, first = enrichment.hunter_lookup(domain, s)
                if not email:
                    email = enrichment.site_email_lookup(domain)
                    contact = "Public site email" if email else ""
            lead = {
                "dedupe_key": item["dedupe_key"],
                "brand_name": verdict.get("brand_name") or item.get("brand_name") or "Brand",
                "platform": item["platform"], "source_url": item["source_url"], "brand_domain": domain,
                "niche": item["niche"], "contact_email": email, "decision_maker": contact, "first_name": first,
                "intent_score": int(verdict.get("intent_score", 60)),
                "competition_level": verdict.get("competition_level", "Low"),
                "raw_snippet": item.get("snippet", ""), "hook_concepts": verdict.get("hook_concepts", ""),
                "email_subject": verdict.get("email_subject", ""), "step1_body": verdict.get("step1_body", ""),
                "step2_body": verdict.get("step2_body", ""), "step3_body": verdict.get("step3_body", ""),
            }
            if repo.save_lead(lead):
                added += 1
        note = ""
        if not (s.serper_api_key or s.apify_api_token):
            note = " (SERPER_API_KEY and APIFY_API_TOKEN not configured)"
        text = f"Last scan {clock.ts()} UTC: {len(items)} signals, {added} new qualified leads.{note}"
        repo.set_kv("last_scan", text)
        log.info(text)
        return {"scanned": len(items), "added": added}
    finally:
        _lock.release()


def seed_demo(s: Settings | None = None) -> int:
    """Insert 3 clearly flagged demo leads (never sent in live mode)."""
    s = s or get_settings()
    demos = [
        ("FocusFlow AI", "X (Twitter)", "AI SaaS", "We need 4 UGC creators for paid TikTok and Meta ads. Budget $200/video. Email founders@focusflow.example", "founders@focusflow.example", 88),
        ("Lumina Botanicals", "Meta Ad Library", "skincare", "Lumina Botanicals has 9 active static ads for 21+ days and no native creator video.", "growth@lumina.example", 78),
        ("Kyoto Whisk Co.", "Google Forms Brief", "matcha", "Onboarding 10 paid creators for TikTok Shop, $150-$300 per deliverable.", "partnerships@kyotowhisk.example", 84),
    ]
    added = 0
    for i, (brand, platform, niche, snippet, email, score) in enumerate(demos):
        seq = ai.fallback_sequence(brand, platform, niche, s)
        added += repo.save_lead({
            "dedupe_key": f"demo:{i}", "brand_name": brand, "platform": platform, "source_url": "demo",
            "brand_domain": email.split("@")[1], "niche": niche, "contact_email": email,
            "decision_maker": "Demo contact", "intent_score": score, "raw_snippet": snippet, "is_demo": 1, **seq,
        })
    return added
