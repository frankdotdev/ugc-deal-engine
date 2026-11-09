"""AI lead qualification and email-sequence writing (Gemini), with a rule-based fallback."""
from __future__ import annotations

import json
import logging
import re

from .config import Settings
from .enrichment import EMAIL_RE

log = logging.getLogger(__name__)

CREATOR_PHRASES = (
    "my portfolio", "hire me", "available for ugc", "dm me for ugc", "ugc creator here", "open for collabs",
    "i'm a ugc", "i am a ugc", "my rates", "book me",
)
BUYER_PHRASES = ("looking for", "need ", "hiring", "apply", "application", "roster", "paid", "brief", "budget", "active ad", "seeking")

_client: dict = {"key": None, "client": None, "types": None}


def _gemini(s: Settings):
    if not s.gemini_api_key:
        return None, None
    if _client["key"] != s.gemini_api_key:
        from google import genai
        from google.genai import types
        _client.update(key=s.gemini_api_key, client=genai.Client(api_key=s.gemini_api_key), types=types)
    return _client["client"], _client["types"]


def fallback_sequence(brand: str, platform: str, niche: str, s: Settings) -> dict:
    hooks = (
        f"1. \"POV: you tried every {niche} option and nothing worked until this...\"\n"
        f"2. \"I used {brand} for 7 days straight. Here's the honest result.\""
    )
    return {
        "hook_concepts": hooks,
        "email_subject": f"native video ideas for {brand}",
        "step1_body": (
            f"I came across {brand} on {platform} and had a few ideas for native, vertical video ads.\n\n"
            f"I'm {s.sender_offer}. I sketched 2 short hook concepts for your product (portfolio: {s.portfolio_url}).\n\n"
            "Want me to send them over, no strings attached?"
        ),
        "step2_body": (
            f"Sharing the 2 hook concepts I mentioned so you can test them with your team:\n\n{hooks}\n\n"
            "I can film and edit either one with native captions in about 48 hours. Open to a single-video test this week?"
        ),
        "step3_body": (
            "I'll close the loop so I don't clutter your inbox. If you need fast-turnaround UGC ads later, "
            "just reply and I'll send my rates."
        ),
    }


def _rule_based(item: dict, s: Settings, snippet: str, low: str) -> dict | None:
    is_ad = item.get("signal_type") == "ads"
    if not is_ad and not any(p in low for p in BUYER_PHRASES):
        return None
    score = 55 + (15 if ("$" in low or "budget" in low) else 0) + (10 if "paid" in low else 0)
    score += (10 if EMAIL_RE.search(snippet) else 0) + (5 if is_ad else 0)
    platform, niche = item.get("platform", "Web"), item.get("niche", "DTC")
    brand = item.get("brand_name") or (item.get("title") or "your brand")[:40]
    return {
        "brand_name": brand, "intent_score": min(score, 95), "inferred_domain": "",
        "competition_level": "Medium" if platform in ("X (Twitter)", "LinkedIn Posts") else "Low",
        **fallback_sequence(brand, platform, niche, s),
    }


def qualify(item: dict, s: Settings) -> dict | None:
    """Return qualification + sequence for a buyer lead, or None to discard."""
    snippet = f"{item.get('title', '')} - {item.get('snippet', '')}"
    low = snippet.lower()
    if any(p in low for p in CREATOR_PHRASES):
        return None
    client, types = _gemini(s)
    if client is None:
        return _rule_based(item, s, snippet, low)

    platform, niche = item.get("platform", "Web"), item.get("niche", "DTC")
    is_ad = item.get("signal_type") == "ads"
    prompt = f"""You qualify UGC sales leads and write cold outreach for {s.sender_offer}.
Record:
- Platform: {platform}
- Niche: {niche}
- Signal type: {'active paid ads (hypothesis: they may need fresh creator video)' if is_ad else 'public post / brief / form'}
- URL: {item.get('source_url')}
- Text: {snippet}

Rules:
1. is_valid_buyer = true only if this is a brand, founder, agency or advertiser hiring UGC creators or actively advertising. False for creators advertising themselves, job-seekers, news, or irrelevant pages.
2. intent_score 1-100 (urgency, budget mentioned, direct hiring language). competition_level: Ultra-Low, Low or Medium.
3. Write ONLY from facts in the record. Never invent claims about their ads, results, products or past conversations.
4. Plain text emails, no greeting line and no signature (added automatically). Each body under 75 words.
   - email_subject: lowercase, 4-7 words, specific.
   - step1_body: 3 sentences: relevant observation, value (offer 2 tailored hook concepts, portfolio {s.portfolio_url}), low-friction question.
   - hook_concepts: 2 specific 3-second video hook scripts for their product.
   - step2_body: share the 2 hooks as free value + offer a 48-hour test video.
   - step3_body: polite 2-sentence break-up leaving the door open.
Return JSON only:
{{"is_valid_buyer": bool, "brand_name": str, "inferred_domain": str, "intent_score": int, "competition_level": str,
"email_subject": str, "step1_body": str, "hook_concepts": str, "step2_body": str, "step3_body": str}}"""
    try:
        resp = client.models.generate_content(
            model=s.gemini_model, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.25),
        )
        text = re.sub(r"^```(?:json)?|```$", "", resp.text.strip(), flags=re.M).strip()
        out = json.loads(text)
    except Exception as exc:
        log.warning("Gemini qualification failed: %s", exc)
        return None
    if not out.get("is_valid_buyer"):
        return None
    fb = fallback_sequence(out.get("brand_name") or item.get("brand_name") or "your brand", platform, niche, s)
    for key, value in fb.items():
        if not str(out.get(key, "")).strip():
            out[key] = value
    return out
