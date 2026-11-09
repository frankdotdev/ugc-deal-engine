"""Find a contact email and brand domain for a lead."""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from .config import Settings
from .http import session

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BAD_EMAIL_PARTS = (
    "example.com", "sentry.io", "wixpress.com", "email.com", "noreply", "no-reply", "donotreply",
    ".png", ".jpg", ".gif", ".webp", "yourdomain", "domain.com",
)
NON_BRAND_HOSTS = (
    "x.com", "twitter.com", "tiktok.com", "linkedin.com", "docs.google.com", "notion.site", "facebook.com",
    "fb.com", "fb.me", "instagram.com", "linktr.ee", "youtube.com", "bit.ly", "library.tiktok.com",
)
PRIORITY_ROLES = ("marketing", "growth", "founder", "ceo", "creative", "brand", "social", "influencer", "content", "partnership")


def extract_email(text: str) -> str:
    for match in EMAIL_RE.findall(text or ""):
        if not any(bad in match.lower() for bad in BAD_EMAIL_PARTS):
            return match.lower()
    return ""


def clean_domain(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url if url.startswith("http") else f"https://{url}").netloc.lower().replace("www.", "")
    except ValueError:
        return ""
    if not host or any(host == h or host.endswith("." + h) for h in NON_BRAND_HOSTS):
        return ""
    return host


def hunter_lookup(domain: str, s: Settings) -> tuple[str, str, str]:
    """Returns (email, 'Name (Position)', first_name) or empty strings."""
    if not domain or not s.hunter_api_key:
        return "", "", ""
    try:
        r = session().get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": s.hunter_api_key, "limit": 10}, timeout=15,
        )
        if r.status_code != 200:
            return "", "", ""
        emails = r.json().get("data", {}).get("emails", [])
    except Exception as exc:  # network/JSON errors must never break a scan
        log.warning("Hunter lookup failed for %s: %s", domain, exc)
        return "", "", ""
    ranked = sorted(emails, key=lambda e: (
        0 if any(k in (e.get("position") or "").lower() for k in PRIORITY_ROLES) else 1, -(e.get("confidence") or 0)))
    for e in ranked:
        if (e.get("confidence") or 0) >= 70 and e.get("value"):
            name = f"{e.get('first_name') or ''} {e.get('last_name') or ''}".strip()
            position = e.get("position") or "Contact"
            return e["value"].lower(), (f"{name} ({position})" if name else position), (e.get("first_name") or "").title()
    return "", "", ""


def site_email_lookup(domain: str) -> str:
    """Last resort: a public email on the brand's own site."""
    if not domain:
        return ""
    for path in ("", "/contact", "/pages/contact", "/contact-us", "/partnerships"):
        try:
            r = session().get(f"https://{domain}{path}", timeout=8)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        found = [m.lower() for m in EMAIL_RE.findall(r.text) if not any(b in m.lower() for b in BAD_EMAIL_PARTS)]
        same_domain = [m for m in found if m.endswith(domain)]
        if same_domain or found:
            return (same_domain or found)[0]
    return ""
