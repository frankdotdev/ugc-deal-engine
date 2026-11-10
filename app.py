import os

import re

import ssl

import csv

import io

import time

import json

import random

import sqlite3

import logging

import smtplib

import imaplib

from datetime import datetime, timedelta, timezone

from email.message import EmailMessage

from email.utils import make_msgid, formataddr

from urllib.parse import urlparse, unquote, urljoin

import requests

from dotenv import load_dotenv

from flask import Flask, render_template_string, request, redirect, url_for, Response, jsonify

from google import genai

from google.genai import types

from apscheduler.schedulers.background import BackgroundScheduler



load_dotenv()



logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

logger = logging.getLogger("UGCDealEngine")



app = Flask(__name__)

DB_PATH = "ugc_leads.db"



# API & Scraping Keys

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
if GEMINI_MODEL in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", ""):
    GEMINI_MODEL = "gemini-3.8-flash"



# SMTP / IMAP Outreach Configuration

SMTP_SENDER_NAME = os.getenv("SMTP_SENDER_NAME", "Ozomba Ebube Mark | UGC Studio").strip()

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "eozomba@gmail.com").strip()

SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()

SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com").strip()

PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "https://your-portfolio-link.com").strip()

DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", "100"))

AUTO_PILOT_ENABLED = True



gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None



HTTP_HEADERS = {

    "User-Agent": (

        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "

        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    ),

    "Accept-Language": "en-US,en;q=0.9",

}



# ==========================================

# 1. 45+ BUILT-IN TELEGRAM CHANNELS

# ==========================================

DEFAULT_TELEGRAM_CHANNELS = [

    "ugccreators", "ugcjobs", "creatorcasting", "brandbriefs", "influencerjobs",

    "tiktokcreatorscollab", "ugccommunity", "ugcbranddeals", "contentcreatoropps",

    "ugceurope", "tiktokcreatorjobs", "ugcagencydeals", "creatorsconnect",

    "ugclatam", "ugcasia", "brandambassadorjobs", "creatorskit_app", "ugc_jobs",

    "ugcopportunities", "ugccreatorjobs", "influencer_briefs", "tiktokshopcreators",

    "tiktokshopaffiliates", "dtcbrandjobs", "ecommercejobs", "socialmediajobs",

    "remotevideocreators", "prpackages", "giftedcollabs", "paidcollabs",

    "creatorbriefs", "contentcreatorjobs", "ugchiring", "ugccasting",

    "influencercasting", "microinfluencers", "shopifybrands", "saasmarketingjobs",

    "videoadcreators", "reels_creators", "shorts_creators", "ugcwork",

    "branddealsdaily", "creatornetwork", "ugc_uk", "ugc_usa"

]



# ==========================================

# 2. OMNI-PLATFORM INTENT & FORM FILTERS

# ==========================================

SIGNUP_INTENT_REGEX = re.compile(

    r"("

    r"sign\s*-?\s*up|"

    r"apply\s*(here|now|below|today|to\s+join|via|link|for|:)?|"

    r"creator\s+(application|roster|program|network|call|onboarding|form|wanted|needed|search)|"

    r"ugc\s+(application|roster|brief|casting|call|creator\s+form|opportunity|collab|job|gig|project|wanted|needed)|"

    r"application\s+form|"

    r"fill\s+out\s+(the|this|our)?\s*(form|application)|"

    r"join\s+our\s+(creator|ugc|ambassador|affiliate)|"

    r"casting\s+call|"

    r"onboarding\s+(new\s+)?(ugc\s+)?creators|"

    r"register\s+(here|now|below)|"

    r"submit\s+your\s+(portfolio|application|rates|proposal)|"

    r"looking\s+for\s+(paid\s+)?(ugc|tiktok|content|video)\s+creators|"

    r"hiring\s+(ugc|tiktok|content|video)\s+creators|"

    r"need\s+(ugc|tiktok|content)\s+creators|"

    r"paid\s+(ugc|collab|brief|partnership|creator)|"

    r"gifted\s+collab|pr\s+list|ambassador\s+application|freelance\s+ugc"

    r")",

    re.IGNORECASE,

)



FORM_AND_PORTAL_URL_INDICATORS = (

    "docs.google.com/forms", "forms.gle/", "typeform.com", "airtable.com/shr",

    "airtable.com/app", "tally.so", "jotform.com", "larksuite.com", "feishu.cn",

    "notion.site", "notion.so", "fillout.com", "paperform.co", "share.hsforms.com",

    "forms.clickup.com", "forms.monday.com", "coda.io",

    "/pages/collab", "/pages/creators", "/pages/ambassador", "/pages/ugc",

    "/pages/affiliate", "/pages/partnerships", "/pages/apply", "/pages/casting",

    "upwork.com/freelance-jobs", "contra.com", "backstage.com/casting",

    "castingnetworks.com", "apply.workable.com", "boards.greenhouse.io",

    "jobs.lever.co", "jobs.ashbyhq.com", "breezy.hr", "wellfound.com",

    "peopleperhour.com", "freelancer.com", "mandy.com",

    "joinbrands.com", "billo.app", "insense.pro", "cohley.com", "collabstr.com",

    "promote.sh", "sideshift.app", "jointrybe.com", "socialync.io",

    "creator.co", "useallies.com", "passionfroot.me", "linktr.ee", "beacons.ai",

    "stan.store", "bento.me", "t.me/", "reddit.com/r/ugccreators"

)





def has_signup_intent(item: dict) -> bool:

    combined_text = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('raw_snippet', '')}"

    source_url = (item.get("source_url") or "").lower()



    creator_self_promo = (

        "hire me as your ugc", "my ugc portfolio is open", "i am a ugc creator looking for work",

        "[for hire]", "for hire: ugc creator"

    )

    if any(p in combined_text.lower() for p in creator_self_promo):

        return False



    if any(ind in source_url for ind in FORM_AND_PORTAL_URL_INDICATORS):

        return True



    return bool(SIGNUP_INTENT_REGEX.search(combined_text))





# ==========================================

# 3. DATABASE LAYER

# ==========================================

def init_db():

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.cursor()

        cursor.execute("""

            CREATE TABLE IF NOT EXISTS leads (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                brand_name TEXT,

                platform TEXT,

                source_url TEXT UNIQUE,

                brand_domain TEXT,

                niche TEXT,

                region TEXT DEFAULT 'Global',

                contact_email TEXT,

                decision_maker TEXT,

                intent_score INTEGER,

                competition_level TEXT,

                raw_snippet TEXT,

                ai_pitch TEXT,

                hook_concepts TEXT,

                status TEXT DEFAULT 'New',

                created_at TEXT,

                email_subject TEXT DEFAULT '',

                followup_1_body TEXT DEFAULT '',

                followup_2_body TEXT DEFAULT '',

                sequence_step INTEGER DEFAULT 0,

                last_sent_at TEXT DEFAULT '',

                next_followup_at TEXT DEFAULT '',

                message_id_header TEXT DEFAULT '',

                replied INTEGER DEFAULT 0,

                form_autofilled INTEGER DEFAULT 0,

                autofill_log TEXT DEFAULT '',

                freelance_proposal TEXT DEFAULT '',

                short_dm_pitch TEXT DEFAULT '',

                bid_strategy TEXT DEFAULT '',

                proposal_applied INTEGER DEFAULT 0

            )

        """)

        existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(leads)").fetchall()}

        migrations = {

            "region": "TEXT DEFAULT 'Global'",

            "email_subject": "TEXT DEFAULT ''",

            "followup_1_body": "TEXT DEFAULT ''",

            "followup_2_body": "TEXT DEFAULT ''",

            "sequence_step": "INTEGER DEFAULT 0",

            "last_sent_at": "TEXT DEFAULT ''",

            "next_followup_at": "TEXT DEFAULT ''",

            "message_id_header": "TEXT DEFAULT ''",

            "replied": "INTEGER DEFAULT 0",

            "form_autofilled": "INTEGER DEFAULT 0",

            "autofill_log": "TEXT DEFAULT ''",

            "freelance_proposal": "TEXT DEFAULT ''",

            "short_dm_pitch": "TEXT DEFAULT ''",

            "bid_strategy": "TEXT DEFAULT ''",

            "proposal_applied": "INTEGER DEFAULT 0",

        }

        for col, col_def in migrations.items():

            if col not in existing_cols:

                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {col_def}")



        cursor.execute("""

            CREATE TABLE IF NOT EXISTS send_logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                lead_id INTEGER,

                step_number INTEGER,

                recipient TEXT,

                sent_date TEXT,

                sent_timestamp TEXT

            )

        """)



        cursor.execute("""

            CREATE TABLE IF NOT EXISTS telegram_channels (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                handle TEXT UNIQUE

            )

        """)

        for ch in DEFAULT_TELEGRAM_CHANNELS:

            cursor.execute("INSERT OR IGNORE INTO telegram_channels (handle) VALUES (?)", (ch,))



        cursor.execute("""

            CREATE TABLE IF NOT EXISTS creator_profile (

                id INTEGER PRIMARY KEY CHECK (id = 1),

                full_name TEXT,

                email TEXT,

                phone TEXT,

                portfolio_url TEXT,

                tiktok_handle TEXT,

                instagram_handle TEXT,

                country TEXT,

                standard_rate TEXT,

                niches TEXT,

                bio_pitch TEXT

            )

        """)

        cursor.execute("""

            INSERT OR IGNORE INTO creator_profile (

                id, full_name, email, phone, portfolio_url, tiktok_handle,

                instagram_handle, country, standard_rate, niches, bio_pitch

            ) VALUES (

                1,

                ?,

                ?,

                '+1 / WhatsApp Available',

                ?,

                '@yourtiktokhandle',

                '@yourighandle',

                'Remote / Global',

                '$150 per UGC video (48hr turnaround)',

                'SaaS, AI Apps, Skincare, E-Commerce, Tech, Health & Wellness',

                'Direct-response UGC creator specializing in high-converting 3-second TikTok & Meta ad hooks with 48-hour delivery.'

            )

        """, (

            SMTP_SENDER_NAME.split("|")[0].strip() or "Ozomba Ebube Mark",

            SMTP_EMAIL or "eozomba@gmail.com",

            PORTFOLIO_URL,

        ))

        conn.commit()





def get_creator_profile() -> dict:

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute("SELECT * FROM creator_profile WHERE id = 1").fetchone()

        return dict(row) if row else {}





def get_tracked_channels() -> list[str]:

    with sqlite3.connect(DB_PATH) as conn:

        rows = conn.execute("SELECT handle FROM telegram_channels ORDER BY id ASC").fetchall()

        return [r[0] for r in rows]





def get_today_send_count() -> int:

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with sqlite3.connect(DB_PATH) as conn:

        row = conn.execute("SELECT COUNT(*) FROM send_logs WHERE sent_date = ?", (today_str,)).fetchone()

        return row[0] if row else 0





def record_send_log(lead_id: int, step_number: int, recipient: str):

    now = datetime.now(timezone.utc)

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(

            "INSERT INTO send_logs (lead_id, step_number, recipient, sent_date, sent_timestamp) VALUES (?, ?, ?, ?, ?)",

            (lead_id, step_number, recipient, now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d %H:%M:%S"))

        )

        conn.commit()





# ==========================================

# 4. STRICT EMAIL VALIDATOR, MX CHECKER & FALSE-POSITIVE BLOCKER

# ==========================================

EMAIL_REGEX = re.compile(r"(?<![a-zA-Z0-9._%+-])([a-zA-Z0-9._%+-]{2,40}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,10})\b")

MAILTO_REGEX = re.compile(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,10})", re.IGNORECASE)

# Only match explicit bracketed [at] or (at), NEVER plain English " at " (which caused "Sign up at domain.com" -> up@domain.com)

STRICT_OBFUSCATED_REGEX = re.compile(

    r"\b(hello|info|contact|collab|collabs|ugc|creator|creators|partnerships|partnership|marketing|growth|pr|press|talent|casting|support|team|brand|founders|founder)\s*(?:\[at\]|\(at\))\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,10})\b",

    re.IGNORECASE,

)



# English words that get accidentally glued before @ or caught in bad scrapes (like "up@scoutmadeugc.com")

FALSE_POSITIVE_USER_PREFIXES = {

    "up", "out", "in", "on", "to", "by", "us", "me", "it", "at", "or", "an", "as", "be", "do", "go", "if", "is", "no", "of", "so", "we",

    "now", "here", "more", "live", "shop", "join", "visit", "available", "online", "posted", "hosted", "located", "found",

    "view", "see", "look", "check", "back", "start", "today", "link", "form", "page", "site", "web", "http", "https", "www",

    "u003e", "u003c", "u0026", "nbsp", "quot", "amp", "2x", "3x", "4x", "1x", "png", "jpg", "svg", "css", "js"

}



BLOCKED_EMAIL_DOMAINS = (

    "example.com", "sentry.io", "wixpress.com", "email.com", "domain.com",

    "yoursite.com", "company.com", "google.com", "typeform.com", "airtable.com",

    "notion.so", "cloudflare.com", "w3.org", "schema.org", "github.com",

    "upwork.com", "fiverr.com", "reddit.com", "linktr.ee", "beacons.ai",

    "tiktok.com", "instagram.com", "facebook.com", "x.com", "twitter.com",

    "gstatic.com", "googleapis.com", "googleusercontent.com"

)

BLOCKED_EXTENSIONS = (

    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",

    ".woff", ".woff2", ".ttf", ".mp4", ".mp3", ".pdf", ".zip"

)



MX_CACHE: dict[str, bool] = {}





def domain_has_mx_record(domain: str) -> bool:

    """

    Uses Google's free DNS-over-HTTPS API to verify the domain actually has valid

    Mail Exchange (MX) servers before we ever attempt to send an email to it.

    """

    if not domain or "." not in domain:

        return False

    domain = domain.lower().strip()

    if domain in MX_CACHE:

        return MX_CACHE[domain]



    try:

        resp = requests.get(

            "https://dns.google/resolve",

            params={"name": domain, "type": "MX"},

            timeout=4,

        )

        if resp.status_code == 200:

            data = resp.json()

            answers = data.get("Answer", [])

            has_mx = any(ans.get("type") == 15 for ans in answers)

            MX_CACHE[domain] = has_mx

            return has_mx

    except Exception:

        # If offline or DNS check times out, don't block valid-looking domains

        return True

    MX_CACHE[domain] = False

    return False





def is_valid_deliverable_email(email: str, check_mx: bool = False) -> bool:

    """

    Strict validation gate:

    Rejects 'up@scoutmadeugc.com', short 2-letter prepositions, image filenames,

    blocked domains, and domains without MX records.

    """

    if not email or "@" not in email:

        return False



    e = email.lower().strip().strip(".,;:'\"()[]{}<>?!/\\|")

    # Remove leading HTML escape artifacts like u003e or 3d

    e = re.sub(r"^(?:u003[ce]|u0022|3d)+", "", e)



    if "@" not in e or len(e) > 65 or len(e) < 6:

        return False



    user_part, domain_part = e.split("@", 1)



    if not user_part or not domain_part or "." not in domain_part:

        return False



    # Reject false-positive prefixes like "up@", "out@", "now@", "here@"

    if user_part in FALSE_POSITIVE_USER_PREFIXES:

        return False



    # Reject purely numeric prefixes or 1-2 character prefixes unless 'pr' or 'hr'

    if user_part.isdigit():

        return False

    if len(user_part) <= 2 and user_part not in ("pr", "hr", "hi", "ai"):

        return False



    if any(e.endswith(ext) or domain_part.endswith(ext) for ext in BLOCKED_EXTENSIONS):

        return False

    if any(b in domain_part for b in BLOCKED_EMAIL_DOMAINS):

        return False

    if any(bad in user_part for bad in ("noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster", "bounce", "privacy", "legal", "dmca", "abuse")):

        return False



    tld = domain_part.rsplit(".", 1)[-1]

    if len(tld) < 2 or not tld.isalpha():

        return False



    if check_mx and not domain_has_mx_record(domain_part):

        return False



    return True





def clean_and_validate_emails(raw_text: str, check_mx: bool = False) -> list[str]:

    if not raw_text:

        return []



    decoded = unquote(raw_text[:200000]).replace("&#64;", "@").replace("\\u0040", "@").replace("\\u003e", " ")



    candidates = []

    # 1. Prioritize explicit mailto: links first (highest accuracy on brand websites)

    for m in MAILTO_REGEX.findall(decoded):

        candidates.append(m)



    # 2. Standard @ emails

    for m in EMAIL_REGEX.findall(decoded):

        candidates.append(m)



    # 3. Strict bracketed [at] / (at) obfuscations only

    for user_part, domain_part in STRICT_OBFUSCATED_REGEX.findall(decoded):

        candidates.append(f"{user_part}@{domain_part}")



    valid = []

    for raw_e in candidates:

        e = raw_e.lower().strip().strip(".,;:'\"()[]{}<>?!/\\|")

        e = re.sub(r"^(?:u003[ce]|u0022|3d)+", "", e)

        if is_valid_deliverable_email(e, check_mx=check_mx) and e not in valid:

            valid.append(e)



    priority = (

        "partnership", "collab", "ugc", "creator", "casting", "talent",

        "marketing", "growth", "pr", "press", "brand", "founder", "hello", "contact", "info"

    )

    valid.sort(key=lambda x: next((i for i, k in enumerate(priority) if k in x.split("@")[0]), 99))

    return valid





def extract_email_from_text(text: str, check_mx: bool = True) -> str:

    emails = clean_and_validate_emails(text, check_mx=check_mx)

    return emails[0] if emails else ""





def extract_clean_domain(url: str) -> str:

    if not url:

        return ""

    try:

        parsed = urlparse(url if url.startswith("http") else f"https://{url}")

        host = parsed.netloc.lower().replace("www.", "")

        non_brand_hosts = (

            "x.com", "twitter.com", "tiktok.com", "linkedin.com",

            "docs.google.com", "forms.gle", "notion.site", "notion.so",

            "facebook.com", "instagram.com", "threads.net", "typeform.com",

            "airtable.com", "tally.so", "jotform.com", "larksuite.com",

            "feishu.cn", "t.me", "linktr.ee", "beacons.ai", "stan.store",

            "bento.me", "reddit.com", "youtube.com", "upwork.com", "fiverr.com",

            "contra.com", "backstage.com", "castingnetworks.com", "wellfound.com",

            "peopleperhour.com", "freelancer.com", "apply.workable.com",

            "boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com",

            "breezy.hr", "fillout.com", "paperform.co", "coda.io",

            "share.hsforms.com", "forms.clickup.com", "forms.monday.com",

            "joinbrands.com", "billo.app", "insense.pro", "cohley.com",

            "collabstr.com", "promote.sh", "sideshift.app", "jointrybe.com",

            "socialync.io", "creator.co", "useallies.com", "passionfroot.me"

        )

        if any(s in host for s in non_brand_hosts):

            return ""

        return host

    except Exception:

        return ""





def extract_external_domains_from_html(html: str) -> list[str]:

    urls = re.findall(r"https?://[^\s\"'<>\\]+", html or "")

    domains = []

    for u in urls:

        d = extract_clean_domain(u)

        if d and "." in d and not any(x in d for x in ("gstatic.com", "googleapis.com", "googleusercontent.com", "w3.org", "apple.com", "play.google.com")):

            if d not in domains:

                domains.append(d)

    return domains





def deep_scrape_url_for_email_and_domain(url: str) -> tuple[str, str]:

    if not url or not url.startswith("http"):

        return "", ""

    try:

        resp = requests.get(url, headers=HTTP_HEADERS, timeout=8, allow_redirects=True)

        if resp.status_code == 200 and resp.text:

            emails = clean_and_validate_emails(resp.text, check_mx=True)

            found_email = emails[0] if emails else ""

            found_domain = extract_clean_domain(resp.url)

            if not found_domain:

                ext_domains = extract_external_domains_from_html(resp.text)

                if ext_domains:

                    found_domain = ext_domains[0]

            if not found_domain and found_email:

                email_dom = found_email.split("@")[-1]

                if email_dom not in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"):

                    found_domain = email_dom

            return found_email, found_domain

    except Exception:

        pass

    return "", ""





def crawl_brand_domain_for_email(domain: str) -> tuple[str, str]:

    if not domain or not domain_has_mx_record(domain):

        return "", ""

    paths_to_check = [

        "", "/pages/contact", "/contact", "/pages/collab", "/pages/creators",

        "/pages/ambassador", "/policies/terms-of-service", "/policies/privacy-policy"

    ]

    for path in paths_to_check:

        target = f"https://{domain}{path}"

        try:

            resp = requests.get(target, headers=HTTP_HEADERS, timeout=6, allow_redirects=True)

            if resp.status_code == 200 and resp.text:

                emails = clean_and_validate_emails(resp.text, check_mx=True)

                if emails:

                    return emails[0], f"Verified MX from {domain}{path or '/'}"

        except Exception:

            continue

    return "", ""





def free_duckduckgo_search(query: str, max_results: int = 18) -> list[dict]:

    results = []

    try:

        resp = requests.post(

            "https://html.duckduckgo.com/html/",

            data={"q": query},

            headers=HTTP_HEADERS,

            timeout=10,

        )

        if resp.status_code == 200:

            blocks = re.findall(

                r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',

                resp.text,

                re.DOTALL,

            )

            for link, title_html, snippet_html in blocks[:max_results]:

                clean_link = unquote(link)

                if "uddg=" in clean_link:

                    clean_link = unquote(clean_link.split("uddg=")[-1].split("&")[0])

                clean_title = re.sub(r"<[^>]+>", "", title_html).strip()

                clean_snip = re.sub(r"<[^>]+>", "", snippet_html).strip()

                if clean_link.startswith("http"):

                    results.append({"title": clean_title, "snippet": clean_snip, "link": clean_link})

    except Exception:

        pass

    return results





def find_email_without_hunter(snippet: str, source_url: str, domain: str, brand_name: str) -> tuple[str, str, str]:

    email = extract_email_from_text(snippet, check_mx=True)

    if email:

        if not domain and email.split("@")[-1] not in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com"):

            domain = email.split("@")[-1]

        return email, "Verified Snippet Email (MX OK)", domain



    form_email, form_domain = deep_scrape_url_for_email_and_domain(source_url)

    if form_domain and not domain:

        domain = form_domain

    if form_email:

        return form_email, "Verified from Form/Page HTML (MX OK)", domain



    if domain:

        crawled_email, source_label = crawl_brand_domain_for_email(domain)

        if crawled_email:

            return crawled_email, source_label, domain



    if domain and domain_has_mx_record(domain):

        dork_query = f'"@{domain}" (partnerships OR collab OR marketing OR ugc OR hello OR contact)'

        for hit in free_duckduckgo_search(dork_query, max_results=5):

            found = extract_email_from_text(f"{hit.get('title', '')} {hit.get('snippet', '')}", check_mx=True)

            if found and found.endswith(f"@{domain}"):

                return found, "Verified Web Search (MX OK)", domain



    return "", "Use Proposal Helper / Form Auto-Filler", domain





def sanitize_corrupted_emails_in_db() -> int:

    """

    Runs automatically on boot:

    Scans your existing database for false-positive emails like 'up@scoutmadeugc.com'

    (caused by 'Sign up at ...'), halts their sequences so they never bounce again,

    and attempts to replace them with a verified email from the brand's actual website.

    """

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute("SELECT id, brand_name, contact_email, source_url, brand_domain, raw_snippet FROM leads").fetchall()



    cleaned_count = 0

    for r in rows:

        curr_email = (r["contact_email"] or "").strip()

        if "@" not in curr_email:

            continue



        if not is_valid_deliverable_email(curr_email, check_mx=True):

            logger.info(f"Removing invalid/bouncing email from Lead #{r['id']}: {curr_email}")

            # Try to find a real verified email on that domain

            real_email, dm_label, resolved_dom = find_email_without_hunter(

                r["raw_snippet"] or "",

                r["source_url"] or "",

                r["brand_domain"] or curr_email.split("@")[-1],

                r["brand_name"] or "",

            )

            with sqlite3.connect(DB_PATH) as conn:

                if real_email and is_valid_deliverable_email(real_email, check_mx=True):

                    conn.execute(

                        "UPDATE leads SET contact_email = ?, decision_maker = ?, sequence_step = 0, next_followup_at = '', status = 'New (Email Repaired)' WHERE id = ?",

                        (real_email, dm_label, r["id"]),

                    )

                else:

                    conn.execute(

                        "UPDATE leads SET contact_email = 'Use Proposal Helper / Form Auto-Filler', decision_maker = 'Invalid Email Removed', sequence_step = 0, next_followup_at = '', status = 'New' WHERE id = ?",

                        (r["id"],),

                    )

                conn.commit()

            cleaned_count += 1



    return cleaned_count





def backfill_missing_emails() -> int:

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        missing = conn.execute(

            "SELECT id, brand_name, source_url, brand_domain, raw_snippet FROM leads WHERE contact_email NOT LIKE '%@%'"

        ).fetchall()



    enriched_count = 0

    for row in missing:

        email, dm_label, resolved_domain = find_email_without_hunter(

            row["raw_snippet"] or "",

            row["source_url"] or "",

            row["brand_domain"] or "",

            row["brand_name"] or "",

        )

        if email and is_valid_deliverable_email(email, check_mx=True):

            with sqlite3.connect(DB_PATH) as conn:

                conn.execute(

                    "UPDATE leads SET contact_email = ?, decision_maker = ?, brand_domain = COALESCE(NULLIF(brand_domain, ''), ?) WHERE id = ?",

                    (email, dm_label, resolved_domain, row["id"]),

                )

                conn.commit()

            enriched_count += 1

            if AUTO_PILOT_ENABLED:

                send_sequence_step(row["id"])

    return enriched_count





# ==========================================

# 5. PLATFORM-AWARE FREELANCE PROPOSAL & BID GENERATOR

# ==========================================

def build_freelance_proposal_pack(

    brand_name: str,

    platform: str,

    niche: str,

    source_url: str,

    hooks: str,

    raw_snippet: str = "",

) -> dict:

    profile = get_creator_profile()

    creator_name = profile.get("full_name") or "Ozomba Ebube Mark"

    portfolio = profile.get("portfolio_url") or PORTFOLIO_URL

    base_rate = profile.get("standard_rate") or "$150 per UGC video (48hr turnaround)"

    url_lower = (source_url or "").lower()

    plat_lower = (platform or "").lower()



    if not hooks:

        hooks = (

            f"• Hook 1 (Pattern Interrupt): \"Stop scrolling if you've been looking for a {niche} that actually delivers...\"\n"

            f"• Hook 2 (7-Day POV Test): \"I tested {brand_name} for 7 days straight—here is my honest review.\""

        )



    if any(k in url_lower or k in plat_lower for k in ("upwork", "peopleperhour", "freelancer")):

        bid_strategy = "Suggested Upwork Bid: $150 (1-Video Test + 2 Hook Variations) | $390 (3-Video Ad Bundle) • 48-Hr Turnaround"

        proposal = (

            f"Hi! Direct-response UGC portfolio reel right here so you don't have to hunt for it: {portfolio}\n\n"

            f"I saw your Upwork brief for {brand_name} ({niche}) and already mapped out 2 scroll-stopping 3-second hooks you can test immediately:\n"

            f"{hooks}\n\n"

            f"What's included in my 48-hour turnaround package:\n"

            f"• 1x Fully edited 9:16 vertical ad (native captions, b-roll, & clear CTA)\n"

            f"• 2x Swappable 3-second opening hook variations to lower your CPA\n"

            f"• All raw unedited footage + full paid ad usage rights\n\n"

            f"If you send over the product/app details today, I can have the scripts locked in within 4 hours. Want to start with a 1-video test milestone?\n\n"

            f"Best,\n{creator_name}"

        )

    elif any(k in url_lower or k in plat_lower for k in ("contra", "wellfound", "workable", "greenhouse", "lever", "ashby", "breezy", "linkedin")):

        bid_strategy = "Suggested Contra / Retainer Pitch: $150/video Test | $500/mo (4 High-Converting TikTok/Meta Ads + Hook Variations)"

        proposal = (

            f"Hey {brand_name} Growth Team,\n\n"

            f"Portfolio & recent high-converting TikTok/Meta ad creatives: {portfolio}\n\n"

            f"I specialize in direct-response UGC that blends native creator storytelling with performance ad structure. "

            f"For {brand_name} ({niche}), here are 2 immediate 3-second hook angles I'd test first:\n"

            f"{hooks}\n\n"

            f"Why brands work with me:\n"

            f"• Fast 48-hour turnaround from brief/product receipt\n"

            f"• Every deliverable includes 2 hook variations + raw + captioned cuts for A/B testing\n"

            f"• Rate: {base_rate}\n\n"

            f"Open to kicking off with a single test creative this week?\n\n"

            f"— {creator_name}"

        )

    elif any(k in url_lower or k in plat_lower for k in ("backstage", "castingnetworks", "mandy", "casting")):

        bid_strategy = f"Casting Submission Rate: {base_rate} (Includes Perpetual Organic + 365-Day Paid Whitelisting/Spark Ad Rights)"

        proposal = (

            f"CASTING SUBMISSION — {creator_name} (Direct-Response UGC & On-Camera Spokesperson)\n"

            f"On-Camera Reel & UGC Portfolio: {portfolio}\n\n"

            f"Hi {brand_name} Casting Team,\n"

            f"I'd love to be considered for your {niche} UGC production. I shoot in 4K 60fps with studio-grade lavalier/shotgun audio, natural & controlled softbox lighting, and deliver both raw takes and fully captioned vertical edits within 48 hours.\n\n"

            f"Two 3-second cold-open reads I can film as self-tape/test hooks:\n"

            f"{hooks}\n\n"

            f"Available immediately for remote self-tape or fast product turnaround ({profile.get('country', 'Remote')}).\n"

            f"Contact: {profile.get('email')} | {profile.get('phone')}"

        )

    else:

        bid_strategy = f"Standard Package: {base_rate} | 3-Pack Hook Testing Bundle: $395 (6 total hook variations)"

        proposal = (

            f"Hey {brand_name} team! Here is my 60-sec UGC portfolio reel: {portfolio}\n\n"

            f"Saw your call for {niche} creators and put together 2 custom 3-second hook concepts specifically for your product:\n"

            f"{hooks}\n\n"

            f"I can shoot, edit (with native TikTok/Reels captions + b-roll), and deliver both hook variations + all raw files within 48 hours. "

            f"Would love to jump on your current test batch!\n\n"

            f"— {creator_name} ({profile.get('email')})"

        )



    short_dm = (

        f"Hey {brand_name}! Saw your {niche} UGC creator call. Here's my 60s ad reel: {portfolio} — "

        f"I also drafted 2 custom 3-sec hooks to help lower your CPA and can deliver in 48 hrs ({base_rate}). "

        f"Mind if I send the script ideas over?"

    )



    return {

        "freelance_proposal": proposal,

        "short_dm_pitch": short_dm,

        "bid_strategy": bid_strategy,

    }





def backfill_freelance_proposals() -> int:

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute(

            "SELECT id, brand_name, platform, niche, source_url, hook_concepts, raw_snippet FROM leads WHERE freelance_proposal = '' OR freelance_proposal IS NULL"

        ).fetchall()



    updated = 0

    for r in rows:

        pack = build_freelance_proposal_pack(

            r["brand_name"] or "Brand Team",

            r["platform"] or "UGC Brief",

            r["niche"] or "DTC / App",

            r["source_url"] or "",

            r["hook_concepts"] or "",

            r["raw_snippet"] or "",

        )

        with sqlite3.connect(DB_PATH) as conn:

            conn.execute(

                "UPDATE leads SET freelance_proposal = ?, short_dm_pitch = ?, bid_strategy = ? WHERE id = ?",

                (pack["freelance_proposal"], pack["short_dm_pitch"], pack["bid_strategy"], r["id"]),

            )

            conn.commit()

        updated += 1

    return updated





# ==========================================

# 6. AUTOMATED FORM AUTO-FILLER

# ==========================================

def map_label_to_profile_value(label_text: str, profile: dict, lead: dict) -> str:

    l = (label_text or "").lower()

    if any(k in l for k in ("email", "e-mail", "mail")):

        return profile.get("email", "")

    if any(k in l for k in ("phone", "whatsapp", "mobile", "number", "tel")):

        return profile.get("phone", "")

    if any(k in l for k in ("tiktok", "tik tok")):

        return profile.get("tiktok_handle", "")

    if any(k in l for k in ("instagram", "ig handle", "insta")):

        return profile.get("instagram_handle", "")

    if any(k in l for k in ("portfolio", "website", "reel", "sample", "work link", "examples", "media kit", "url", "link")):

        return profile.get("portfolio_url", "")

    if any(k in l for k in ("rate", "price", "budget", "cost", "fee", "compensation", "charge")):

        return profile.get("standard_rate", "$150 per video")

    if any(k in l for k in ("country", "location", "city", "where are you", "based", "address", "state", "region")):

        return profile.get("country", "Remote / Global")

    if any(k in l for k in ("niche", "category", "industry", "topics")):

        return profile.get("niches", "SaaS, Tech, Skincare, E-Commerce")

    if any(k in l for k in ("why", "pitch", "proposal", "cover letter", "about you", "tell us", "experience", "message", "note", "anything else", "hook", "idea")):

        return lead.get("freelance_proposal") or f"{lead.get('ai_pitch', '')}\n\n2 Custom Hooks:\n{lead.get('hook_concepts', '')}".strip() or profile.get("bio_pitch", "")

    if any(k in l for k in ("first name", "given name")):

        return (profile.get("full_name") or "Creator").split()[0]

    if any(k in l for k in ("last name", "surname", "family name")):

        parts = (profile.get("full_name") or "Creator").split()

        return parts[-1] if len(parts) > 1 else parts[0]

    if any(k in l for k in ("name", "creator", "who are you")):

        return profile.get("full_name", "")

    return profile.get("portfolio_url", "")





def autofill_google_form_direct(form_url: str, profile: dict, lead: dict) -> tuple[bool, str]:

    try:

        resp = requests.get(form_url, headers=HTTP_HEADERS, timeout=12, allow_redirects=True)

        if resp.status_code != 200:

            return False, f"Google Form returned HTTP {resp.status_code}"



        final_url = resp.url

        html = resp.text

        payload = {}



        if 'name="emailAddress"' in html:

            payload["emailAddress"] = profile.get("email", "")



        match = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?\]);\s*</script>", html, re.DOTALL)

        if match:

            try:

                data = json.loads(match.group(1))

                questions = data[1][1] if (len(data) > 1 and data[1] and len(data[1]) > 1) else []

                for q in questions:

                    if not isinstance(q, list) or len(q) < 5:

                        continue

                    q_label = str(q[1] or "")

                    q_details = q[4]

                    if isinstance(q_details, list) and len(q_details) > 0 and isinstance(q_details[0], list):

                        entry_id = q_details[0][0]

                        options_list = q_details[0][1] if len(q_details[0]) > 1 else None

                        field_key = f"entry.{entry_id}"

                        if isinstance(options_list, list) and len(options_list) > 0 and isinstance(options_list[0], list) and options_list[0][0]:

                            payload[field_key] = str(options_list[0][0])

                        else:

                            payload[field_key] = map_label_to_profile_value(q_label, profile, lead)

            except Exception as e:

                logger.debug(f"FB_PUBLIC_LOAD_DATA_ parse fallback: {e}")



        for entry_num in re.findall(r'name="entry\.(\d+)"', html):

            key = f"entry.{entry_num}"

            if key not in payload:

                payload[key] = f"{profile.get('full_name')} | {profile.get('email')} | {profile.get('portfolio_url')}"



        if not payload:

            return False, "Google Form requires Google Sign-In or has no public entry fields."



        submit_url = re.sub(r"/viewform.*", "/formResponse", final_url)

        if "/formResponse" not in submit_url:

            submit_url = final_url.rstrip("/") + "/formResponse"



        post_headers = {

            **HTTP_HEADERS,

            "Referer": final_url,

            "Origin": "https://docs.google.com",

            "Content-Type": "application/x-www-form-urlencoded",

        }

        post_resp = requests.post(submit_url, data=payload, headers=post_headers, timeout=12)

        if post_resp.status_code in (200, 302):

            return True, f"Submitted {len(payload)} fields to Google Form (/formResponse HTTP {post_resp.status_code})"

        return False, f"Google Form POST returned HTTP {post_resp.status_code} (filled {len(payload)} fields)"

    except Exception as e:

        return False, f"Google Form submit error: {e}"





def autofill_with_playwright_or_html(url: str, profile: dict, lead: dict) -> tuple[bool, str]:

    try:

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)

            page = browser.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=20000)

            page.wait_for_timeout(2500)



            inputs = page.query_selector_all("input:not([type='hidden']):not([type='submit']):not([type='checkbox']):not([type='radio']), textarea")

            filled_count = 0

            for inp in inputs:

                try:

                    if not inp.is_visible():

                        continue

                    placeholder = inp.get_attribute("placeholder") or ""

                    name_attr = inp.get_attribute("name") or ""

                    aria_label = inp.get_attribute("aria-label") or ""

                    inp_type = (inp.get_attribute("type") or "text").lower()

                    hint = f"{placeholder} {name_attr} {aria_label} {inp_type}"



                    val = map_label_to_profile_value(hint, profile, lead)

                    inp.fill(val)

                    filled_count += 1

                except Exception:

                    continue



            submit_btn = page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Apply'), button:has-text('Send')")

            if submit_btn and submit_btn.is_visible():

                submit_btn.click()

                page.wait_for_timeout(2000)



            browser.close()

            if filled_count > 0:

                return True, f"Playwright Headless Browser auto-filled {filled_count} fields & submitted!"

    except ImportError:

        pass

    except Exception as e:

        logger.debug(f"Playwright auto-fill fallback: {e}")



    try:

        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10, allow_redirects=True)

        if resp.status_code == 200 and "<form" in resp.text.lower():

            action_match = re.search(r'<form[^>]*action=["\']([^"\']*)["\']', resp.text, re.I)

            action_url = urljoin(resp.url, action_match.group(1)) if action_match else resp.url

            input_names = re.findall(r'<(?:input|textarea)[^>]*name=["\']([^"\']+)["\']', resp.text, re.I)

            if input_names:

                payload = {name: map_label_to_profile_value(name, profile, lead) for name in set(input_names)}

                post_resp = requests.post(action_url, data=payload, headers=HTTP_HEADERS, timeout=10)

                if post_resp.status_code in (200, 201, 204, 302):

                    return True, f"HTML Form Submitter posted {len(payload)} fields (HTTP {post_resp.status_code})"

    except Exception as e:

        return False, f"Form auto-fill error: {e}"



    return False, "Use '⚡ Copy Proposal & Open Job ↗' to paste your ready-made proposal directly!"





def autofill_lead_form(lead_id: int) -> tuple[bool, str]:

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()



    if not lead:

        return False, "Lead not found."



    lead_dict = dict(lead)

    profile = get_creator_profile()

    url = (lead_dict.get("source_url") or "").strip()



    if "docs.google.com/forms" in url or "forms.gle/" in url:

        ok, msg = autofill_google_form_direct(url, profile, lead_dict)

    else:

        ok, msg = autofill_with_playwright_or_html(url, profile, lead_dict)



    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    with sqlite3.connect(DB_PATH) as conn:

        if ok:

            conn.execute(

                "UPDATE leads SET form_autofilled = 1, autofill_log = ?, status = CASE WHEN status = 'New' THEN 'Form Auto-Filled ✅' ELSE status END WHERE id = ?",

                (f"{now_str}: {msg}", lead_id),

            )

        else:

            conn.execute("UPDATE leads SET autofill_log = ? WHERE id = ?", (f"{now_str}: {msg}", lead_id))

        conn.commit()



    return ok, msg





def bulk_autofill_all_forms(limit: int = 25) -> dict:

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute("""

            SELECT id, source_url FROM leads

            WHERE form_autofilled = 0

              AND (

                  source_url LIKE '%docs.google.com/forms%'

                  OR source_url LIKE '%forms.gle%'

                  OR source_url LIKE '%airtable.com%'

                  OR source_url LIKE '%typeform.com%'

                  OR source_url LIKE '%tally.so%'

                  OR source_url LIKE '%jotform.com%'

                  OR source_url LIKE '%/pages/collab%'

                  OR source_url LIKE '%/pages/creators%'

              )

            ORDER BY id DESC LIMIT ?

        """, (limit,)).fetchall()



    success_count = 0

    for r in rows:

        ok, _ = autofill_lead_form(r["id"])

        if ok:

            success_count += 1

    return {"attempted": len(rows), "filled": success_count}





# ==========================================

# 7. AI SIGN-UP VERIFIER & SEQUENCE GENERATOR

# ==========================================

def infer_region(text: str, url: str) -> str:

    combined = f"{text} {url}".lower()

    if any(k in combined for k in ("t.me/", "telegram")):

        return "Telegram Channels"

    if any(k in combined for k in (

        "upwork.com", "contra.com", "fiverr.com", "peopleperhour", "freelancer.com",

        "wellfound.com", "workable.com", "greenhouse.io", "lever.co", "ashbyhq.com",

        "backstage.com", "castingnetworks.com", "joinbrands.com", "billo.app",

        "insense.pro", "cohley.com", "collabstr.com", "sideshift.app", "jointrybe.com"

    )):

        return "Freelance & Job Boards"

    if any(k in combined for k in ("larksuite", "feishu", "china", "shenzhen", "hong kong", "singapore", "asia", "shopee", "lazada", ".cn", ".sg", ".jp", ".kr")):

        return "Asia / China DTC"

    if any(k in combined for k in ("uk", "united kingdom", "london", "europe", "germany", "france", "spain", "netherlands", "€", "£", ".co.uk", ".de", ".eu", ".fr")):

        return "Europe"

    if any(k in combined for k in ("usa", "us only", "united states", "canada", "north america", "latam", "brazil", "mexico", "new york", "los angeles", "austin", "$")):

        return "Americas"

    return "Global"





def build_default_sequence(brand_name: str, platform: str, niche: str, hooks: str) -> dict:

    subject = f"just applied for {brand_name}'s UGC creator call + 2 hook ideas"

    step1 = (

        f"Hey {brand_name} team,\n\n"

        f"I just saw your {platform} call for UGC creators in the {niche} space and submitted my application.\n\n"

        f"To make things easy for your creative team, I also mapped out 2 custom 3-second hook concepts tailored to your product. "

        f"Here is my 60-sec portfolio reel: {PORTFOLIO_URL}\n\n"

        f"Mind if I send over those two script ideas right here?"

    )

    step2 = (

        f"Hey team — following up on my creator application! Here are the 2 custom 3-second hook concepts I put together for {brand_name}:\n\n"

        f"{hooks}\n\n"

        f"I can film and deliver both variations with raw + captioned files within 48 hours ({PORTFOLIO_URL}). "

        f"Would love to hop on your next test batch!"

    )

    step3 = (

        f"Hey {brand_name} team — closing the loop on my creator application so I don't clutter your inbox. "

        f"Whenever you onboard your next round of UGC creators, just reply 'UGC' and we can get started!"

    )

    return {"email_subject": subject, "ai_pitch": step1, "followup_1_body": step2, "followup_2_body": step3}





def analyze_and_craft_pitch(raw_item: dict, fast_mode: bool = False) -> dict | None:

    if not has_signup_intent(raw_item):

        return None



    snippet = f"{raw_item.get('title', '')} - {raw_item.get('snippet', '')}"

    platform = raw_item.get("platform", "Sign-Up Form")

    niche = raw_item.get("niche", "DTC / App")



    clean_title = (raw_item.get("title") or "Brand Creator Call").split(" - ")[0].split(" | ")[0][:42].strip()

    brand_guess = raw_item.get("brand_name") or clean_title or "Brand Team"

    hooks = (

        f"1. Pattern Interrupt: 'Stop scrolling if you've been looking for a {niche} that actually delivers...'\n"

        f"2. Honest Test POV: 'I tested {brand_guess} for 7 days straight—here is my honest review.'"

    )

    default_seq = build_default_sequence(brand_guess, platform, niche, hooks)



    if fast_mode or not gemini_client:

        return {

            "is_valid_signup_call": True,

            "brand_name": brand_guess,

            "inferred_domain": raw_item.get("brand_domain", ""),

            "intent_score": random.randint(86, 97),

            "competition_level": "Low",

            "hook_concepts": hooks,

            **default_seq

        }



    prompt = f"""

    Analyze this UGC creator sign-up form, freelance job, or casting call:

    - Platform: {platform}

    - Niche: {niche}

    - Source URL: {raw_item.get('source_url')}

    - Text Content: {snippet}

    - Portfolio Link: {PORTFOLIO_URL}



    Return strict JSON:

    {{

      "is_valid_signup_call": boolean,

      "brand_name": string,

      "inferred_domain": string,

      "intent_score": integer,

      "competition_level": string,

      "email_subject": string,

      "ai_pitch": string,

      "hook_concepts": string,

      "followup_1_body": string,

      "followup_2_body": string

    }}

    """

    try:

        response = gemini_client.models.generate_content(

            model=GEMINI_MODEL,

            contents=prompt,

            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),

        )

        parsed = json.loads(response.text)

        if not parsed.get("is_valid_signup_call"):

            return None

        return parsed

    except Exception:

        return {

            "is_valid_signup_call": True,

            "brand_name": brand_guess,

            "inferred_domain": raw_item.get("brand_domain", ""),

            "intent_score": 90,

            "competition_level": "Low",

            "hook_concepts": hooks,

            **default_seq

        }





def save_lead(lead_data: dict) -> int | None:

    try:

        with sqlite3.connect(DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

                INSERT OR IGNORE INTO leads (

                    brand_name, platform, source_url, brand_domain, niche, region,

                    contact_email, decision_maker, intent_score, competition_level,

                    raw_snippet, ai_pitch, hook_concepts, status, created_at,

                    email_subject, followup_1_body, followup_2_body,

                    freelance_proposal, short_dm_pitch, bid_strategy

                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', ?, ?, ?, ?, ?, ?, ?)

            """, (

                lead_data.get("brand_name", "Unknown Brand"),

                lead_data.get("platform", "Sign-Up Form"),

                lead_data.get("source_url", ""),

                lead_data.get("brand_domain", ""),

                lead_data.get("niche", "General"),

                lead_data.get("region", "Global"),

                lead_data.get("contact_email", ""),

                lead_data.get("decision_maker", ""),

                int(lead_data.get("intent_score", 90)),

                lead_data.get("competition_level", "Low"),

                lead_data.get("raw_snippet", ""),

                lead_data.get("ai_pitch", ""),

                lead_data.get("hook_concepts", ""),

                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),

                lead_data.get("email_subject", ""),

                lead_data.get("followup_1_body", ""),

                lead_data.get("followup_2_body", ""),

                lead_data.get("freelance_proposal", ""),

                lead_data.get("short_dm_pitch", ""),

                lead_data.get("bid_strategy", ""),

            ))

            conn.commit()

            if cursor.rowcount > 0:

                return cursor.lastrowid

    except Exception as e:

        logger.error(f"Database error saving lead: {e}")

    return None





# ==========================================

# 8. 70+ OMNI-PLATFORM QUERIES & HYPER-HARVESTER

# ==========================================

GLOBAL_SIGNUP_QUERIES = [

    {"platform": "Google Forms", "niche": "Direct Brand Application", "region": "Global", "q": 'site:docs.google.com/forms ("UGC" OR "Content Creator") ("sign up" OR "apply" OR "application" OR "rates" OR "portfolio")'},

    {"platform": "Google Forms", "niche": "Paid Collab Roster", "region": "Americas", "q": 'site:docs.google.com/forms ("UGC creator" OR "TikTok creator") ("email" OR "collab" OR "PR" OR "paid")'},

    {"platform": "Google Forms", "niche": "Skincare & Beauty UGC", "region": "Global", "q": 'site:docs.google.com/forms ("skincare" OR "beauty" OR "makeup" OR "cosmetics" OR "haircare") ("UGC" OR "creator application")'},

    {"platform": "Google Forms", "niche": "App, AI & SaaS UGC", "region": "Americas", "q": 'site:docs.google.com/forms ("app" OR "SaaS" OR "AI" OR "software" OR "startup") ("UGC" OR "creator" OR "TikTok")'},

    {"platform": "Google Forms", "niche": "Fitness, Health & Supplements", "region": "Americas", "q": 'site:docs.google.com/forms ("fitness" OR "supplement" OR "wellness" OR "nutrition" OR "protein" OR "matcha") ("UGC" OR "creator")'},

    {"platform": "Google Forms", "niche": "Fashion, Jewelry & Apparel", "region": "Global", "q": 'site:docs.google.com/forms ("fashion" OR "clothing" OR "jewelry" OR "apparel" OR "activewear") ("UGC" OR "creator" OR "ambassador")'},

    {"platform": "Google Forms", "niche": "Pet, Home & Kitchen DTC", "region": "Americas", "q": 'site:docs.google.com/forms ("pet" OR "dog" OR "cat" OR "home" OR "kitchen" OR "coffee") ("UGC" OR "creator application")'},

    {"platform": "Google Forms", "niche": "Gaming, FinTech & Crypto", "region": "Global", "q": 'site:docs.google.com/forms ("gaming" OR "fintech" OR "finance" OR "crypto" OR "web3") ("UGC" OR "content creator")'},

    {"platform": "Google Forms", "niche": "UGC Agency Roster", "region": "Global", "q": 'site:docs.google.com/forms ("agency" OR "roster" OR "casting") ("UGC" OR "TikTokAds" OR "paid social") ("portfolio")'},

    {"platform": "Typeform Roster", "niche": "Brand Creator Roster", "region": "Global", "q": 'site:typeform.com ("UGC" OR "creator application" OR "creator roster" OR "content creator") ("apply" OR "sign up" OR "portfolio")'},

    {"platform": "Typeform Roster", "niche": "DTC Brand Casting", "region": "Americas", "q": 'site:typeform.com ("TikTok" OR "Reels") ("UGC" OR "paid collab" OR "brand ambassador")'},

    {"platform": "Airtable Portal", "niche": "Agency & Brand Casting", "region": "Americas", "q": 'site:airtable.com ("UGC" OR "creator roster" OR "casting call" OR "creator application" OR "brand brief")'},

    {"platform": "Airtable Portal", "niche": "Creator Database Sign-Up", "region": "Global", "q": 'site:airtable.com ("submit your portfolio" OR "creator onboarding" OR "tiktok creator") ("UGC")'},

    {"platform": "Tally.so Form", "niche": "Creator Onboarding", "region": "Europe", "q": 'site:tally.so ("UGC" OR "creator application" OR "creator roster" OR "paid collab" OR "tiktok creator")'},

    {"platform": "Jotform / Fillout", "niche": "Brand Application Form", "region": "Global", "q": '(site:jotform.com OR site:fillout.com OR site:paperform.co) ("UGC" OR "creator application" OR "content creator" OR "casting call")'},

    {"platform": "HubSpot / ClickUp / Monday", "niche": "Agency Creator Intake", "region": "Americas", "q": '(site:share.hsforms.com OR site:forms.clickup.com OR site:forms.monday.com OR site:coda.io) ("UGC" OR "creator" OR "influencer")'},

    {"platform": "Notion Brief", "niche": "Direct Brand Brief", "region": "Global", "q": '(site:notion.site OR site:notion.so) ("UGC" OR "creator") ("apply" OR "sign up" OR "application" OR "brief" OR "roster")'},

    {"platform": "Lark / Feishu Form", "niche": "Asia / China DTC Brand", "region": "Asia / China DTC", "q": '(site:larksuite.com OR site:feishu.cn) ("UGC" OR "creator" OR "influencer" OR "TikTok" OR "collab")'},

    {"platform": "Upwork UGC Job", "niche": "Freelance UGC Contract", "region": "Freelance & Job Boards", "q": 'site:upwork.com/freelance-jobs ("UGC" OR "TikTok video" OR "UGC creator" OR "unboxing video" OR "spokesperson")'},

    {"platform": "Contra Opportunity", "niche": "Commission-Free Freelance", "region": "Freelance & Job Boards", "q": 'site:contra.com ("UGC" OR "TikTok creator" OR "short form video" OR "content creator") ("apply" OR "hiring" OR "opportunity")'},

    {"platform": "Backstage Casting", "niche": "Paid UGC Casting Call", "region": "Freelance & Job Boards", "q": 'site:backstage.com/casting ("UGC" OR "TikTok" OR "content creator" OR "social media ad")'},

    {"platform": "Casting Networks / Mandy", "niche": "Commercial & UGC Casting", "region": "Freelance & Job Boards", "q": '(site:castingnetworks.com OR site:mandy.com) ("UGC" OR "social media" OR "TikTok" OR "content creator")'},

    {"platform": "Workable / Greenhouse", "niche": "Brand In-House / Contract UGC", "region": "Freelance & Job Boards", "q": '(site:apply.workable.com OR site:boards.greenhouse.io) ("UGC Creator" OR "TikTok Creator" OR "Content Creator")'},

    {"platform": "Lever / Ashby / BreezyHR", "niche": "Startup & DTC Creator Role", "region": "Freelance & Job Boards", "q": '(site:jobs.lever.co OR site:jobs.ashbyhq.com OR site:breezy.hr) ("UGC" OR "TikTok Creator" OR "Content Creator")'},

    {"platform": "Wellfound Startup Job", "niche": "Funded Startup UGC", "region": "Freelance & Job Boards", "q": 'site:wellfound.com ("UGC" OR "TikTok creator" OR "short-form video" OR "creator marketing")'},

    {"platform": "PeoplePerHour / Freelancer", "niche": "Freelance Video Brief", "region": "Freelance & Job Boards", "q": '(site:peopleperhour.com OR site:freelancer.com) ("UGC" OR "TikTok ad" OR "Instagram Reel" OR "unboxing")'},

    {"platform": "LinkedIn Jobs", "niche": "Remote UGC Contract", "region": "Freelance & Job Boards", "q": 'site:linkedin.com/jobs ("UGC Creator" OR "TikTok Content Creator" OR "Freelance UGC")'},

    {"platform": "JoinBrands / Billo / Insense", "niche": "UGC Marketplace Brief", "region": "Freelance & Job Boards", "q": '(site:joinbrands.com OR site:billo.app OR site:insense.pro OR site:cohley.com) ("UGC" OR "brand" OR "brief" OR "apply")'},

    {"platform": "Collabstr / Promote / SideShift", "niche": "Paid Creator Campaign", "region": "Freelance & Job Boards", "q": '(site:collabstr.com OR site:promote.sh OR site:sideshift.app OR site:jointrybe.com OR site:socialync.io) ("UGC" OR "creator")'},

    {"platform": "Creator.co / UseAllies / Passionfroot", "niche": "Brand Campaign Portal", "region": "Freelance & Job Boards", "q": '(site:creator.co OR site:useallies.com OR site:passionfroot.me) ("UGC" OR "campaign" OR "collab" OR "creators")'},

    {"platform": "Linktree / Beacons / Stan", "niche": "Brand Bio Sign-Up Link", "region": "Global", "q": '(site:linktr.ee OR site:beacons.ai OR site:stan.store OR site:bento.me) ("UGC" OR "creator application" OR "apply to be a creator" OR "PR application")'},

    {"platform": "Shopify Collab Portal", "niche": "Direct DTC Brand", "region": "Americas", "q": '(inurl:/pages/collab OR inurl:/pages/collaborate OR inurl:/pages/creators) ("UGC" OR "TikTok" OR "content creator") ("apply" OR "sign up" OR "form")'},

    {"platform": "Brand Ambassador Portal", "niche": "Direct DTC Roster", "region": "Global", "q": '(inurl:/pages/ambassador OR inurl:/pages/ugc OR inurl:/pages/partnerships OR inurl:/pages/casting) ("UGC" OR "TikTok") ("apply" OR "email")'},

    {"platform": "UK & Europe DTC Portal", "niche": "Europe E-Com Brand", "region": "Europe", "q": '("UGC creator" OR "UGC application" OR "creator roster") ("apply" OR "sign up") ("UK" OR "Europe" OR "London" OR "Germany" OR "£" OR "€")'},

    {"platform": "Asia Cross-Border DTC", "niche": "Shenzhen / Singapore DTC", "region": "Asia / China DTC", "q": '("UGC creator" OR "TikTok Shop creator") ("apply" OR "sign up" OR "form" OR "email") ("Shenzhen" OR "Singapore" OR "Hong Kong" OR "Asia")'},

    {"platform": "X (Twitter) Casting", "niche": "DTC Founder / Agency", "region": "Americas", "q": 'site:x.com ("looking for" OR "need" OR "hiring" OR "casting") ("UGC creator" OR "UGC creators") ("apply" OR "form" OR "email" OR "portfolio")'},

    {"platform": "X (Twitter) Paid Brief", "niche": "Paid Ads Creative", "region": "Global", "q": 'site:x.com ("paid UGC" OR "UGC brief" OR "creator roster") ("drop your portfolio" OR "send rates" OR "sign up" OR "@")'},

    {"platform": "TikTok Casting Call", "niche": "TikTok Shop / Brand", "region": "Global", "q": 'site:tiktok.com ("looking for ugc creators" OR "ugc casting call" OR "creator application") ("apply" OR "sign up" OR "bio" OR "email")'},

    {"platform": "LinkedIn Posts", "niche": "CMO / Agency Casting", "region": "Global", "q": 'site:linkedin.com/posts ("looking for UGC" OR "hiring UGC creators" OR "UGC casting call") ("apply" OR "email" OR "form" OR "portfolio")'},

    {"platform": "Instagram / Threads Call", "niche": "Brand Social Casting", "region": "Global", "q": '(site:instagram.com OR site:threads.net) ("looking for UGC creators" OR "UGC casting call" OR "creator application form") ("apply" OR "link in bio" OR "email")'},

    {"platform": "Reddit r/UGCcreators", "niche": "Direct Reddit Hiring Post", "region": "Freelance & Job Boards", "q": 'site:reddit.com/r/UGCcreators ("[Hiring]" OR "looking for" OR "hiring" OR "paid" OR "apply" OR "form")'},

    {"platform": "Facebook / YouTube", "niche": "Video Ad Creator Call", "region": "Global", "q": '(site:facebook.com OR site:youtube.com) ("UGC creators wanted" OR "looking for UGC creators" OR "UGC application form") ("apply" OR "email")'},

]





def scrape_reddit_direct_json() -> list[dict]:

    endpoints = [

        "https://www.reddit.com/r/UGCcreators/new.json?limit=50",

        "https://www.reddit.com/r/UGCcreators/search.json?q=hiring+OR+paid+OR+looking+for+OR+apply+OR+form&restrict_sr=on&sort=new&limit=50",

        "https://www.reddit.com/search.json?q=%22UGC+creator%22+%28hiring+OR+apply+OR+%22sign+up%22+OR+paid+OR+brief%29&sort=new&limit=50",

    ]

    discovered = []

    seen = set()



    for ep in endpoints:

        try:

            resp = requests.get(ep, headers=HTTP_HEADERS, timeout=10)

            if resp.status_code == 200:

                children = resp.json().get("data", {}).get("children", [])

                for child in children:

                    post = child.get("data", {})

                    title = post.get("title", "")

                    selftext = post.get("selftext", "")

                    permalink = f"https://www.reddit.com{post.get('permalink', '')}"

                    url_overridden = post.get("url_overridden_by_dest") or permalink



                    if any(x in title.lower() for x in ("[for hire]", "for hire:", "my portfolio", "rate my portfolio")):

                        continue



                    combined = f"{title} {selftext}"

                    if permalink not in seen and re.search(r"(hiring|looking for|need|apply|sign up|form|paid|brief|brand|agency|collab|@)", combined, re.I):

                        seen.add(permalink)

                        ext_domains = extract_external_domains_from_html(selftext)

                        discovered.append({

                            "platform": "Reddit (r/UGCcreators)",

                            "niche": "Direct Brand / Agency Post",

                            "region": "Freelance & Job Boards",

                            "title": title[:90],

                            "snippet": selftext[:350] or title,

                            "source_url": url_overridden if "docs.google.com" in url_overridden or "typeform" in url_overridden or "airtable" in url_overridden else permalink,

                            "brand_domain": ext_domains[0] if ext_domains else extract_clean_domain(url_overridden),

                        })

        except Exception as e:

            logger.debug(f"Reddit JSON scrape warning: {e}")



    return discovered





def scrape_multi_engine_signals(deep_mode: bool = False, target_lead_count: int = 220) -> list[dict]:

    discovered = []

    seen_urls = set()



    for r_item in scrape_reddit_direct_json():

        seen_urls.add(r_item["source_url"])

        discovered.append(r_item)



    queries_to_run = list(GLOBAL_SIGNUP_QUERIES)



    if deep_mode:

        extra_niches = [

            "skincare", "beauty", "supplement", "fitness app", "AI tool", "SaaS",

            "pet brand", "coffee", "matcha", "jewelry", "haircare", "baby brand",

            "home decor", "tech gadget", "mobile game", "fintech", "activewear", "oral care"

        ]

        for n in extra_niches:

            queries_to_run.append({

                "platform": f"Google Forms ({n.title()})",

                "niche": n.title(),

                "region": "Global",

                "q": f'site:docs.google.com/forms "{n}" ("UGC" OR "creator" OR "TikTok" OR "collab")'

            })

            queries_to_run.append({

                "platform": f"Upwork / Contra ({n.title()})",

                "niche": n.title(),

                "region": "Freelance & Job Boards",

                "q": f'(site:upwork.com/freelance-jobs OR site:contra.com OR site:backstage.com/casting) "{n}" ("UGC" OR "TikTok" OR "video")'

            })



    pages_to_fetch = [1, 2] if deep_mode else [1]

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}



    for item in queries_to_run:

        if len(discovered) >= target_lead_count and not deep_mode:

            break



        if SERPER_API_KEY:

            for page_num in pages_to_fetch:

                try:

                    payload_dict = {"q": item["q"], "num": 10, "page": page_num}

                    resp = requests.post(

                        "https://google.serper.dev/search",

                        headers=headers,

                        data=json.dumps(payload_dict),

                        timeout=9,

                    )

                    if resp.status_code == 200:

                        organic = resp.json().get("organic", [])

                        if not organic:

                            break

                        for res in organic:

                            link = res.get("link", "")

                            if not link or link in seen_urls:

                                continue

                            seen_urls.add(link)

                            candidate = {

                                "platform": item["platform"],

                                "niche": item["niche"],

                                "region": item.get("region") or infer_region(res.get("snippet", ""), link),

                                "title": res.get("title", ""),

                                "snippet": res.get("snippet", ""),

                                "source_url": link,

                                "brand_domain": extract_clean_domain(link),

                            }

                            if has_signup_intent(candidate):

                                discovered.append(candidate)

                except Exception:

                    pass



        ddg_hits = free_duckduckgo_search(item["q"], max_results=15 if deep_mode else 8)

        for res in ddg_hits:

            link = res.get("link", "")

            if not link or link in seen_urls:

                continue

            seen_urls.add(link)

            candidate = {

                "platform": item["platform"],

                "niche": item["niche"],

                "region": item.get("region") or infer_region(res.get("snippet", ""), link),

                "title": res.get("title", ""),

                "snippet": res.get("snippet", ""),

                "source_url": link,

                "brand_domain": extract_clean_domain(link),

            }

            if has_signup_intent(candidate):

                discovered.append(candidate)



    return discovered





def scrape_telegram_channels_and_search() -> dict:

    channels = get_tracked_channels()

    raw_briefs = []

    seen_urls = set()

    newly_discovered_channels = 0



    tg_queries = [

        'site:t.me/s/ ("UGC" OR "creator") ("apply" OR "sign up" OR "brief" OR "collab" OR "form" OR "email")',

        'site:t.me ("UGC creator" OR "UGC jobs" OR "paid collab" OR "casting call" OR "creator application")',

        'site:t.me ("docs.google.com/forms" OR "typeform.com" OR "airtable.com" OR "notion.site") ("UGC" OR "creator")',

        'site:t.me ("TikTok Shop" OR "brand deal" OR "PR package" OR "gifted collab") ("UGC" OR "creators")',

        'site:t.me ("looking for creators" OR "hiring UGC" OR "send portfolio")',

    ]



    discovered_handles = set()

    for q in tg_queries:

        search_hits = []

        if SERPER_API_KEY:

            try:

                resp = requests.post(

                    "https://google.serper.dev/search",

                    headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},

                    data=json.dumps({"q": q, "num": 10}),

                    timeout=9,

                )

                if resp.status_code == 200:

                    search_hits.extend(resp.json().get("organic", []))

            except Exception:

                pass

        search_hits.extend(free_duckduckgo_search(q, max_results=12))



        for res in search_hits:

            link = res.get("link", "")

            if not link or link in seen_urls:

                continue

            seen_urls.add(link)



            m = re.search(r"t\.me/(?:s/)?([a-zA-Z0-9_]{4,32})", link)

            if m:

                handle_candidate = m.group(1).lower()

                if handle_candidate not in ("share", "joinchat", "addstickers", "proxy", "iv"):

                    discovered_handles.add(handle_candidate)



            raw_briefs.append({

                "platform": "Telegram Channel Brief",

                "niche": "Telegram Casting",

                "region": "Telegram Channels",

                "title": res.get("title", "Telegram UGC Brief"),

                "snippet": res.get("snippet", ""),

                "source_url": link,

                "brand_domain": "",

            })



    if discovered_handles:

        with sqlite3.connect(DB_PATH) as conn:

            cursor = conn.cursor()

            for h in discovered_handles:

                cursor.execute("INSERT OR IGNORE INTO telegram_channels (handle) VALUES (?)", (h,))

                if cursor.rowcount > 0:

                    newly_discovered_channels += 1

            conn.commit()

        channels = get_tracked_channels()



    for ch in channels:

        clean_ch = ch.strip().lstrip("@").split("/")[-1]

        if not clean_ch:

            continue

        preview_url = f"https://t.me/s/{clean_ch}"

        try:

            resp = requests.get(preview_url, headers=HTTP_HEADERS, timeout=7)

            if resp.status_code == 200 and "tgme_widget_message_text" in resp.text:

                msg_blocks = re.findall(

                    r'data-post="([^"]+)"[^>]*>.*?<div class="tgme_widget_message_text[^>]*>(.*?)</div>',

                    resp.text,

                    re.DOTALL,

                )

                for post_id, html_text in msg_blocks[-25:]:

                    clean_text = re.sub(r"<[^>]+>", " ", html_text)

                    clean_text = re.sub(r"\s+", " ", clean_text).strip()

                    post_url = f"https://t.me/{post_id}"

                    if len(clean_text) < 25 or post_url in seen_urls:

                        continue

                    if re.search(r"(ugc|creator|collab|brief|casting|apply|sign up|form|paid|gifted|brand|@|http)", clean_text, re.I):

                        seen_urls.add(post_url)

                        ext_domains = extract_external_domains_from_html(html_text)

                        raw_briefs.append({

                            "platform": f"Telegram (@{clean_ch})",

                            "niche": "Telegram Brief",

                            "region": "Telegram Channels",

                            "title": f"Telegram Brief (@{clean_ch})",

                            "snippet": clean_text[:360],

                            "source_url": post_url,

                            "brand_domain": ext_domains[0] if ext_domains else "",

                        })

        except Exception:

            continue



    saved_count = 0

    for item in raw_briefs:

        if process_and_save_signal(item, fast_mode=True):

            saved_count += 1



    return {

        "channels_scanned": len(channels),

        "new_channels_found": newly_discovered_channels,

        "briefs_found": len(raw_briefs),

        "saved": saved_count,

    }





# ==========================================

# 9. PIPELINE PROCESSOR & AUTO-PILOT SENDER

# ==========================================

def process_and_save_signal(item: dict, forced_email: str = "", fast_mode: bool = False) -> bool:

    ai_eval = analyze_and_craft_pitch(item, fast_mode=fast_mode)

    if not ai_eval:

        return False



    brand_name = ai_eval.get("brand_name") or item.get("brand_name") or "Brand Lead"

    domain = item.get("brand_domain") or ai_eval.get("inferred_domain") or ""



    if forced_email and is_valid_deliverable_email(forced_email, check_mx=True):

        email = forced_email.strip().lower()

        decision_maker = "Manual / Verified MX"

    elif fast_mode:

        email = extract_email_from_text(f"{item.get('title', '')} {item.get('snippet', '')}", check_mx=True)

        decision_maker = "Verified Snippet Email (MX OK)" if email else "Use Proposal Helper / Auto-Filler"

    else:

        email, decision_maker, domain = find_email_without_hunter(

            f"{item.get('title', '')} {item.get('snippet', '')}",

            item.get("source_url", ""),

            domain,

            brand_name,

        )



    hooks = ai_eval.get("hook_concepts", "")

    platform_label = item.get("platform", "Sign-Up Form")

    niche_label = item.get("niche", "DTC")

    source_url = item.get("source_url", "")

    snippet_text = item.get("snippet", "")



    default_seq = build_default_sequence(brand_name, platform_label, niche_label, hooks)

    proposal_pack = build_freelance_proposal_pack(brand_name, platform_label, niche_label, source_url, hooks, snippet_text)

    region = item.get("region") or infer_region(snippet_text, source_url)



    lead_record = {

        "brand_name": brand_name,

        "platform": platform_label,

        "source_url": source_url,

        "brand_domain": domain,

        "niche": niche_label,

        "region": region,

        "contact_email": email or "Use Proposal Helper / Form Auto-Filler",

        "decision_maker": decision_maker or "Creator Partnerships",

        "intent_score": ai_eval.get("intent_score", 90),

        "competition_level": ai_eval.get("competition_level", "Low"),

        "raw_snippet": snippet_text,

        "ai_pitch": ai_eval.get("ai_pitch") or default_seq["ai_pitch"],

        "hook_concepts": hooks,

        "email_subject": ai_eval.get("email_subject") or default_seq["email_subject"],

        "followup_1_body": ai_eval.get("followup_1_body") or default_seq["followup_1_body"],

        "followup_2_body": ai_eval.get("followup_2_body") or default_seq["followup_2_body"],

        "freelance_proposal": proposal_pack["freelance_proposal"],

        "short_dm_pitch": proposal_pack["short_dm_pitch"],

        "bid_strategy": proposal_pack["bid_strategy"],

    }



    new_id = save_lead(lead_record)

    if new_id:

        if AUTO_PILOT_ENABLED and email and is_valid_deliverable_email(email, check_mx=True):

            send_sequence_step(new_id)

        return True

    return False





def run_discovery_pipeline(deep_mode: bool = False) -> dict:

    raw_signals = scrape_multi_engine_signals(deep_mode=deep_mode, target_lead_count=260 if deep_mode else 90)

    added_count = 0

    for item in raw_signals:

        if process_and_save_signal(item, fast_mode=deep_mode):

            added_count += 1



    tg_saved = 0

    if deep_mode:

        tg_stats = scrape_telegram_channels_and_search()

        tg_saved = tg_stats["saved"]



    backfilled = backfill_missing_emails()

    backfill_freelance_proposals()

    return {"scanned": len(raw_signals), "added": added_count + tg_saved, "backfilled": backfilled}





# ==========================================

# 10. SMTP SENDER + IMAP REPLY & BOUNCE DETECTOR

# ==========================================

def check_imap_for_replies_and_bounces() -> tuple[int, int]:

    """

    1. Checks if any lead replied to your emails (marks replied=1, status='Replied').

    2. Checks if mailer-daemon / postmaster bounced any email ('Address not found' / NoSuchUser)

       and automatically halts that sequence so Step 2 & Step 3 never fire to a dead address!

    """

    if not (SMTP_EMAIL and SMTP_APP_PASSWORD):

        return 0, 0

    replied_count = 0

    bounced_count = 0

    try:

        with sqlite3.connect(DB_PATH) as conn:

            conn.row_factory = sqlite3.Row

            active_leads = conn.execute(

                "SELECT id, contact_email, brand_name FROM leads WHERE sequence_step > 0 AND replied = 0 AND status NOT LIKE '%Bounced%'"

            ).fetchall()

        if not active_leads:

            return 0, 0



        mail = imaplib.IMAP4_SSL(IMAP_HOST, 993)

        mail.login(SMTP_EMAIL, SMTP_APP_PASSWORD)

        mail.select("INBOX")



        for lead in active_leads:

            addr = (lead["contact_email"] or "").strip()

            if "@" not in addr:

                continue



            # A. Check for direct reply from the prospect

            status, data = mail.search(None, f'(FROM "{addr}")')

            if status == "OK" and data and data[0]:

                with sqlite3.connect(DB_PATH) as conn:

                    conn.execute(

                        "UPDATE leads SET replied = 1, status = 'Replied', next_followup_at = '' WHERE id = ?",

                        (lead["id"],),

                    )

                    conn.commit()

                replied_count += 1

                continue



            # B. Check for Gmail mailer-daemon bounce mentioning this recipient address

            b_status, b_data = mail.search(None, f'(FROM "mailer-daemon" TEXT "{addr}")')

            if b_status == "OK" and b_data and b_data[0]:

                logger.info(f"Bounce detected for {addr} (Lead #{lead['id']}). Halting sequence.")

                with sqlite3.connect(DB_PATH) as conn:

                    conn.execute(

                        "UPDATE leads SET contact_email = 'Use Proposal Helper / Form Auto-Filler', decision_maker = '⚠️ Bounced Address Removed', next_followup_at = '', status = '⚠️ Bounced (Use Form/Proposal)' WHERE id = ?",

                        (lead["id"],),

                    )

                    conn.commit()

                bounced_count += 1



        mail.logout()

    except Exception as e:

        logger.warning(f"IMAP reply/bounce check warning: {e}")

    return replied_count, bounced_count





def send_sequence_step(lead_id: int) -> tuple[bool, str]:

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()



    if not lead:

        return False, "Lead not found."

    if lead["replied"]:

        return False, "Lead has already replied — sequence stopped."



    recipient = (lead["contact_email"] or "").strip().lower()

    if not is_valid_deliverable_email(recipient, check_mx=True):

        with sqlite3.connect(DB_PATH) as conn:

            conn.execute(

                "UPDATE leads SET contact_email = 'Use Proposal Helper / Form Auto-Filler', decision_maker = 'Blocked Invalid/No-MX Email', next_followup_at = '' WHERE id = ?",

                (lead_id,),

            )

            conn.commit()

        return False, f"Blocked undeliverable/invalid email ({recipient}) before sending — use '⚡ Copy Proposal & Open Job ↗' or '🤖 Auto-Fill Form'!"



    current_step = int(lead["sequence_step"] or 0)

    if current_step >= 3:

        return False, "All 3 sequence steps have already been sent."



    if get_today_send_count() >= DAILY_SEND_LIMIT:

        return False, f"Daily send limit ({DAILY_SEND_LIMIT}) reached."



    next_step = current_step + 1

    base_subject = (lead["email_subject"] or f"just applied for {lead['brand_name']}'s UGC roster").strip()



    if next_step == 1:

        subject = base_subject

        body = lead["ai_pitch"]

        delay_days = 3

        new_status = "Step 1 Sent (Applied + Pitched)"

    elif next_step == 2:

        subject = base_subject if base_subject.lower().startswith("re:") else f"Re: {base_subject}"

        body = lead["followup_1_body"]

        delay_days = 7

        new_status = "Step 2 Sent (Follow-Up 1)"

    else:

        subject = base_subject if base_subject.lower().startswith("re:") else f"Re: {base_subject}"

        body = lead["followup_2_body"]

        delay_days = 0

        new_status = "Step 3 Sent (Sequence Complete)"



    msg = EmailMessage()

    sender_address = SMTP_EMAIL or "demo-sender@localhost"

    msg["From"] = formataddr((SMTP_SENDER_NAME, sender_address))

    msg["To"] = recipient

    msg["Subject"] = subject



    domain_part = sender_address.split("@")[-1] if "@" in sender_address else "ugcengine.local"

    generated_msgid = make_msgid(domain=domain_part)

    msg["Message-ID"] = generated_msgid



    anchor_msgid = lead["message_id_header"] or ""

    if next_step > 1 and anchor_msgid:

        msg["In-Reply-To"] = anchor_msgid

        msg["References"] = anchor_msgid

    else:

        anchor_msgid = generated_msgid



    msg.set_content(body)



    live_sent = False

    if SMTP_EMAIL and SMTP_APP_PASSWORD:

        try:

            context = ssl.create_default_context()

            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=20) as server:

                server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)

                server.send_message(msg)

            live_sent = True

        except Exception as e:

            logger.error(f"SMTP Error sending to {recipient}: {e}")

            return False, f"SMTP Error: {e}"



    now_utc = datetime.now(timezone.utc)

    last_sent_str = now_utc.strftime("%Y-%m-%d %H:%M")

    next_followup_str = (now_utc + timedelta(days=delay_days)).strftime("%Y-%m-%d %H:%M") if delay_days > 0 else ""



    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("""

            UPDATE leads

            SET sequence_step = ?,

                last_sent_at = ?,

                next_followup_at = ?,

                message_id_header = ?,

                status = ?

            WHERE id = ?

        """, (next_step, last_sent_str, next_followup_str, anchor_msgid, new_status, lead_id))

        conn.commit()



    record_send_log(lead_id, next_step, recipient)

    mode_tag = "Live SMTP (MX Verified)" if live_sent else "Simulated"

    return True, f"Sent Step {next_step}/3 via {mode_tag} to {recipient}"





def send_all_ready_leads() -> int:

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        ready_rows = conn.execute(

            "SELECT id FROM leads WHERE sequence_step = 0 AND replied = 0 AND contact_email LIKE '%@%' AND status != 'Archived'"

        ).fetchall()



    sent_c = 0

    for row in ready_rows:

        if get_today_send_count() >= DAILY_SEND_LIMIT:

            break

        ok, _ = send_sequence_step(row["id"])

        if ok:

            sent_c += 1

            if SMTP_EMAIL and SMTP_APP_PASSWORD:

                time.sleep(random.uniform(1.2, 2.8))

    return sent_c





def process_scheduled_outreach_queue() -> dict:

    replies_found, bounces_found = check_imap_for_replies_and_bounces()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")



    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        due_leads = conn.execute("""

            SELECT id FROM leads

            WHERE sequence_step IN (1, 2)

              AND replied = 0

              AND next_followup_at != ''

              AND next_followup_at <= ?

              AND status NOT IN ('Replied', 'Closed Won', 'Archived')

              AND status NOT LIKE '%Bounced%'

        """, (now_str,)).fetchall()



    sent_followups = 0

    for row in due_leads:

        if get_today_send_count() >= DAILY_SEND_LIMIT:

            break

        ok, _ = send_sequence_step(row["id"])

        if ok:

            sent_followups += 1

            if SMTP_EMAIL and SMTP_APP_PASSWORD:

                time.sleep(random.uniform(1.2, 2.8))



    return {"replies_detected": replies_found, "bounces_halted": bounces_found, "followups_sent": sent_followups}





# ==========================================

# 11. COMPLETE DASHBOARD UI & ROUTES

# ==========================================

DASHBOARD_HTML = """

<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <title>UGC Sign-Up Hunter, Form Auto-Filler & Proposal Apply Engine</title>

    <script src="https://cdn.tailwindcss.com"></script>

    <style>

        body { background-color: #FAF7F2; color: #2C2523; font-family: Inter, system-ui, sans-serif; }

        .card-surface { background-color: #FFFFFF; border: 1px solid #E6DEC8; }

        .gold-badge { background-color: #F6EEDB; color: #8A6421; border: 1px solid #DFC68D; }

        .btn-dark { background-color: #261C15; color: #FAF7F2; }

        .btn-dark:hover { background-color: #3D2E24; }

        .btn-outline { background-color: #FAF7F2; color: #2C2523; border: 1px solid #D5C7B2; }

        .btn-outline:hover { background-color: #EFE8DC; }

        .btn-gold { background-color: #8A6421; color: #FFFFFF; }

        .btn-gold:hover { background-color: #6F4F18; }

        .btn-emerald { background-color: #065F46; color: #FFFFFF; }

        .btn-emerald:hover { background-color: #047857; }

        .btn-indigo { background-color: #3730A3; color: #FFFFFF; }

        .btn-indigo:hover { background-color: #312E81; }

    </style>

    <script>

        async function copyProposalAndApply(leadId, elementId, targetUrl, btnElement) {

            const text = document.getElementById(elementId).innerText;

            try {

                await navigator.clipboard.writeText(text);

            } catch (err) {

                const ta = document.createElement("textarea");

                ta.value = text;

                document.body.appendChild(ta);

                ta.select();

                document.execCommand("copy");

                document.body.removeChild(ta);

            }

            btnElement.innerText = "✅ Copied! Opening Job...";

            fetch("/mark-applied/" + leadId, { method: "POST" });

            if (targetUrl) {

                window.open(targetUrl, "_blank");

            }

            setTimeout(() => {

                btnElement.innerText = "✅ Applied (Copy Again ↗)";

            }, 1800);

        }



        async function copyTextOnly(elementId, btnElement) {

            const text = document.getElementById(elementId).innerText;

            await navigator.clipboard.writeText(text);

            const orig = btnElement.innerText;

            btnElement.innerText = "✅ Copied!";

            setTimeout(() => { btnElement.innerText = orig; }, 1400);

        }

    </script>

</head>

<body class="min-h-screen p-5 md:p-8">

    <div class="max-w-7xl mx-auto space-y-6">

        {% if flash_msg %}

        <div class="p-3.5 rounded-xl bg-[#261C15] text-[#FAF7F2] text-xs font-medium flex items-center justify-between shadow">

            <span>● {{ flash_msg }}</span>

            <a href="/" class="text-xs underline text-[#DFC68D]">Dismiss</a>

        </div>

        {% endif %}



        <!-- Top Header & Action Controls -->

        <div class="flex flex-col lg:flex-row lg:items-start justify-between gap-6 border-b border-[#E6DEC8] pb-6">

            <div class="space-y-2 max-w-2xl">

                <div class="flex flex-wrap items-center gap-2">

                    <span class="text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded gold-badge">OMNI-PLATFORM 70+ QUERIES</span>

                    <span class="text-[11px] font-semibold px-2.5 py-0.5 rounded bg-emerald-100 text-emerald-800">🛡️ DNS MX Email Verifier & Bounce Guard Active</span>

                    <span class="text-[11px] font-semibold px-2.5 py-0.5 rounded bg-indigo-100 text-indigo-900">

                        ⚡ 1-Click Proposal Auto-Copy Active

                    </span>

                </div>

                <h1 class="text-3xl font-extrabold tracking-tight text-[#261C15]">UGC Deal Hunter, Form Auto-Filler & Proposal Apply Engine</h1>

                <p class="text-xs text-[#6E6259] leading-relaxed">

                    Scans Google Forms, Typeform, Airtable, Notion, Upwork, Contra, Backstage, JoinBrands, Reddit, X, TikTok, LinkedIn, and 45+ Telegram channels. Verifies MX records before sending, blocks false-positive emails, auto-submits forms, and generates 1-click Upwork/Contra proposals.

                </p>

            </div>



            <!-- Control Buttons -->

            <div class="space-y-2">

                <div class="flex flex-wrap items-center gap-2">

                    <form action="/deep-scan" method="POST" onsubmit="this.querySelector('button').innerText='🚀 Harvesting 200+ Leads...';">

                        <button type="submit" class="btn-dark px-4 py-2 rounded-lg text-xs font-bold shadow-sm">

                            🚀 Hyper-Scan 200+ Leads (All Platforms)

                        </button>

                    </form>

                    <form action="/scan" method="POST" onsubmit="this.querySelector('button').innerText='⏳ Scanning...';">

                        <button type="submit" class="btn-outline px-3.5 py-2 rounded-lg text-xs font-semibold">

                            ↻ Quick Scan

                        </button>

                    </form>

                    <form action="/scan-telegram" method="POST" onsubmit="this.querySelector('button').innerText='⏳ Scanning 45+ TG...';">

                        <button type="submit" class="btn-outline px-3.5 py-2 rounded-lg text-xs font-semibold">

                            ✈️ Scan & Auto-Discover Telegram ({{ tg_channels|length }})

                        </button>

                    </form>

                    <form action="/bulk-autofill" method="POST" onsubmit="this.querySelector('button').innerText='🤖 Auto-Filling Forms...';">

                        <button type="submit" class="btn-emerald px-3.5 py-2 rounded-lg text-xs font-semibold shadow-sm">

                            🤖 Bulk Auto-Fill Forms ({{ unfilled_form_count }})

                        </button>

                    </form>

                </div>

                <div class="flex flex-wrap items-center gap-2">

                    <form action="/sanitize-emails" method="POST" onsubmit="this.querySelector('button').innerText='🛡️ Verifying MX...';">

                        <button type="submit" class="btn-gold px-3 py-1.5 rounded-lg text-xs font-semibold shadow-sm">

                            🛡️ Clean Bad Emails & Verify MX

                        </button>

                    </form>

                    <form action="/enrich-emails" method="POST" onsubmit="this.querySelector('button').innerText='🔍 Crawling...';">

                        <button type="submit" class="btn-outline px-3 py-1.5 rounded-lg text-xs font-semibold">

                            🔍 Deep Enrich Missing Emails ({{ missing_email_count }})

                        </button>

                    </form>

                    <form action="/send-ready" method="POST">

                        <button type="submit" class="btn-outline px-3 py-1.5 rounded-lg text-xs font-semibold">

                            📨 Send Ready Emails ({{ ready_count }})

                        </button>

                    </form>

                    <form action="/run-outreach-queue" method="POST">

                        <button type="submit" class="btn-outline px-3 py-1.5 rounded-lg text-xs font-semibold">

                            📬 Check Replies & Bounces

                        </button>

                    </form>

                    <a href="/export" class="btn-outline px-3 py-1.5 rounded-lg text-xs font-medium inline-block">

                        ⬇ Export CSV

                    </a>

                </div>

            </div>

        </div>



        <!-- Collapsible Creator Profile Settings -->

        <details class="card-surface rounded-xl p-4">

            <summary class="text-xs font-bold text-[#261C15] cursor-pointer flex items-center justify-between">

                <span>🤖 Creator Profile for Form Auto-Filler & Upwork/Contra Proposals ({{ profile.full_name }} • {{ profile.email }} • {{ profile.standard_rate }})</span>

                <span class="text-[11px] font-normal text-amber-800 underline">Configure Profile & Rates ▾</span>

            </summary>

            <form action="/save-profile" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-3 pt-4 mt-3 border-t border-[#E6DEC8]">

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">Full Name</label>

                    <input type="text" name="full_name" value="{{ profile.full_name }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">Email Address</label>

                    <input type="text" name="email" value="{{ profile.email }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">Portfolio / Reel URL</label>

                    <input type="text" name="portfolio_url" value="{{ profile.portfolio_url }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">Phone / WhatsApp</label>

                    <input type="text" name="phone" value="{{ profile.phone }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">TikTok Handle</label>

                    <input type="text" name="tiktok_handle" value="{{ profile.tiktok_handle }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">Instagram Handle</label>

                    <input type="text" name="instagram_handle" value="{{ profile.instagram_handle }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">Location / Shipping Region</label>

                    <input type="text" name="country" value="{{ profile.country }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div>

                    <label class="text-[11px] font-semibold text-[#6E6259]">Standard Rate (Used in Proposals)</label>

                    <input type="text" name="standard_rate" value="{{ profile.standard_rate }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div class="md:col-span-3">

                    <label class="text-[11px] font-semibold text-[#6E6259]">Default Bio / Application Note</label>

                    <input type="text" name="bio_pitch" value="{{ profile.bio_pitch }}" class="w-full text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded px-2.5 py-1.5 mt-0.5" />

                </div>

                <div class="flex items-end">

                    <button type="submit" class="w-full btn-dark py-2 rounded-lg text-xs font-semibold">Save Profile & Rebuild Proposals</button>

                </div>

            </form>

        </details>



        <!-- Instant Lead Drop Bar -->

        <div class="card-surface p-3.5 rounded-xl flex flex-col md:flex-row items-center gap-3">

            <span class="text-xs font-bold text-[#2C2523] whitespace-nowrap">Instant Lead Drop:</span>

            <form action="/instant-drop" method="POST" class="flex-1 flex flex-col md:flex-row items-center gap-2 w-full">

                <input type="text" name="source_url" required placeholder="Paste Upwork/Contra/Backstage job URL, Google Form, or brand portal"

                       class="flex-1 text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded-lg px-3 py-2 w-full" />

                <input type="text" name="direct_email" placeholder="Direct email (optional — MX verified if entered)"

                       class="text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded-lg px-3 py-2 w-full md:w-64" />

                <button type="submit" class="btn-dark px-4 py-2 rounded-lg text-xs font-semibold whitespace-nowrap">

                    Generate Proposal & Send

                </button>

            </form>

        </div>



        <!-- Tracked Telegram Channels Bar -->

        <div class="card-surface p-3.5 rounded-xl space-y-2.5">

            <div class="flex items-center justify-between">

                <span class="text-xs font-bold text-[#2C2523]">✈️ Tracked Telegram Channels ({{ tg_channels|length }} Active — Auto-Discovery Enabled):</span>

            </div>

            <div class="flex flex-wrap items-center gap-1.5 max-h-24 overflow-y-auto pr-1">

                {% for ch in tg_channels %}

                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-[#FAF7F2] border border-[#E6DEC8] text-[#4A3F39]">

                    <a href="https://t.me/s/{{ ch }}" target="_blank" class="hover:underline">@{{ ch }}</a>

                    <form action="/remove-tg/{{ ch }}" method="POST" class="inline">

                        <button type="submit" class="text-[#8C7F75] hover:text-red-700 font-bold ml-0.5">×</button>

                    </form>

                </span>

                {% endfor %}

            </div>

            <form action="/add-tg" method="POST" class="flex items-center justify-end gap-2 pt-1">

                <input type="text" name="handle" required placeholder="Add @channel or t.me/channel"

                       class="text-xs bg-[#FAF7F2] border border-[#E6DEC8] rounded-lg px-3 py-1.5 w-60" />

                <button type="submit" class="btn-outline px-3 py-1.5 rounded-lg text-xs font-semibold">Add & Scan</button>

            </form>

        </div>



        <!-- 6 KPI Cards -->

        <div class="grid grid-cols-2 md:grid-cols-6 gap-3.5">

            <div class="card-surface p-4 rounded-xl shadow-sm">

                <p class="text-[11px] font-bold uppercase tracking-wider text-[#6E6259]">TOTAL LEADS</p>

                <p class="text-3xl font-extrabold mt-1 text-[#261C15]">{{ total_count }}</p>

                <p class="text-[11px] text-[#8C7F75] mt-1">Omni-Platform Pool</p>

            </div>

            <div class="card-surface p-4 rounded-xl shadow-sm">

                <p class="text-[11px] font-bold uppercase tracking-wider text-[#6E6259]">PROPOSALS APPLIED</p>

                <p class="text-3xl font-extrabold mt-1 text-indigo-800">{{ applied_count }}</p>

                <p class="text-[11px] text-[#8C7F75] mt-1">1-Click Copied / Sent</p>

            </div>

            <div class="card-surface p-4 rounded-xl shadow-sm">

                <p class="text-[11px] font-bold uppercase tracking-wider text-[#6E6259]">FORMS AUTO-FILLED</p>

                <p class="text-3xl font-extrabold mt-1 text-emerald-700">{{ autofilled_count }}</p>

                <p class="text-[11px] text-[#8C7F75] mt-1">Submitted by Bot</p>

            </div>

            <div class="card-surface p-4 rounded-xl shadow-sm">

                <p class="text-[11px] font-bold uppercase tracking-wider text-[#6E6259]">MX VERIFIED EMAILS</p>

                <p class="text-3xl font-extrabold mt-1 text-[#261C15]">{{ ready_count }}</p>

                <p class="text-[11px] text-[#8C7F75] mt-1">Ready to Send</p>

            </div>

            <div class="card-surface p-4 rounded-xl shadow-sm">

                <p class="text-[11px] font-bold uppercase tracking-wider text-[#6E6259]">ACTIVE SEQUENCES</p>

                <p class="text-3xl font-extrabold mt-1 text-amber-700">{{ active_seq_count }}</p>

                <p class="text-[11px] text-[#8C7F75] mt-1">Step 1 or 2 Sent</p>

            </div>

            <div class="card-surface p-4 rounded-xl shadow-sm">

                <p class="text-[11px] font-bold uppercase tracking-wider text-[#6E6259]">DAILY QUOTA</p>

                <p class="text-3xl font-extrabold mt-1 text-[#261C15]">{{ sends_today }} / {{ daily_limit }}</p>

                <p class="text-[11px] text-[#8C7F75] mt-1">{{ 'SMTP Live' if smtp_ok else 'Simulated' }}</p>

            </div>

        </div>



        <!-- Region & Source Filter Tabs -->

        <div class="flex flex-wrap items-center gap-2 pt-1">

            <span class="text-xs font-semibold text-[#6E6259] mr-1">Filter Pool:</span>

            {% for r_tab in ['All Regions', 'Freelance & Job Boards', 'Americas', 'Europe', 'Asia / China DTC', 'Telegram Channels', 'Global'] %}

            <a href="/?region={{ r_tab }}"

               class="px-3 py-1.5 rounded-lg text-xs font-semibold transition {% if current_region == r_tab %}btn-dark{% else %}btn-outline{% endif %}">

                {{ r_tab }}{% if r_tab == 'All Regions' %} ({{ total_count }}){% elif r_tab == 'Freelance & Job Boards' %} ({{ freelance_count }}){% endif %}

            </a>

            {% endfor %}

        </div>



        <!-- Leads Cards -->

        <div class="space-y-4">

            {% for lead in leads %}

            <div class="card-surface rounded-xl p-5 shadow-sm">

                <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-[#F0EAE1] pb-4">

                    <div class="space-y-1.5">

                        <div class="flex flex-wrap items-center gap-2">

                            <span class="px-2.5 py-0.5 text-xs font-semibold rounded gold-badge">{{ lead.platform }}</span>

                            <span class="px-2.5 py-0.5 text-xs font-medium rounded bg-stone-100 text-stone-700">{{ lead.region }}</span>

                            <span class="px-2.5 py-0.5 text-xs font-medium rounded bg-emerald-50 text-emerald-800 border border-emerald-200">

                                Match: {{ lead.intent_score }}/100

                            </span>

                            {% if lead.proposal_applied %}

                            <span class="px-2.5 py-0.5 text-xs font-bold rounded bg-indigo-700 text-white">

                                ⚡ Proposal Applied ✅

                            </span>

                            {% endif %}

                            {% if lead.form_autofilled %}

                            <span class="px-2.5 py-0.5 text-xs font-bold rounded bg-emerald-700 text-white">

                                🤖 Form Auto-Filled ✅

                            </span>

                            {% endif %}

                            <span class="px-2.5 py-0.5 text-xs font-semibold rounded {% if lead.replied %}bg-emerald-700 text-white{% elif 'Bounced' in lead.status %}bg-red-100 text-red-800{% elif lead.sequence_step > 0 %}bg-amber-100 text-amber-900{% else %}bg-stone-100 text-stone-700{% endif %}">

                                {% if lead.replied %}

                                    ✅ Replied

                                {% elif 'Bounced' in lead.status %}

                                    {{ lead.status }}

                                {% else %}

                                    Email Step {{ lead.sequence_step }}/3

                                {% endif %}

                            </span>

                        </div>



                        <h2 class="text-lg font-bold text-[#2C2523] pt-1 flex flex-wrap items-center gap-2.5">

                            <span>{{ lead.brand_name }}</span>

                            <a href="{{ lead.source_url }}" target="_blank"

                               class="text-xs font-semibold px-3 py-1 rounded btn-dark inline-flex items-center gap-1">

                                📝 Open Job / Form ↗

                            </a>

                            {% if lead.brand_domain %}

                            <a href="https://{{ lead.brand_domain }}" target="_blank" class="text-xs font-normal text-amber-800 underline">

                                {{ lead.brand_domain }} ↗

                            </a>

                            {% endif %}

                        </h2>



                        {% if lead.bid_strategy %}

                        <p class="text-xs font-semibold text-indigo-900 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded inline-block">

                            💰 {{ lead.bid_strategy }}

                        </p>

                        {% endif %}



                        {% if lead.autofill_log %}

                        <p class="text-[11px] text-emerald-800 font-medium">🤖 Auto-Fill Status: {{ lead.autofill_log }}</p>

                        {% endif %}



                        <form action="/update-email/{{ lead.id }}" method="POST" class="flex flex-wrap items-center gap-2 pt-1">

                            <label class="text-xs font-semibold text-[#6E6259]">Email:</label>

                            <input type="text" name="contact_email" value="{{ lead.contact_email }}"

                                   class="text-xs font-mono bg-[#FAF7F2] border border-[#DFC68D] rounded px-2.5 py-1 w-64 text-[#2C2523]" />

                            <button type="submit" class="text-xs px-2.5 py-1 rounded btn-outline">Verify MX & Send</button>

                            <span class="text-xs text-[#8C7F75]">({{ lead.decision_maker }})</span>

                        </form>

                    </div>



                    <!-- Right Action Buttons -->

                    <div class="flex flex-wrap items-center gap-2">

                        <button type="button"

                                onclick="copyProposalAndApply({{ lead.id }}, 'prop-{{ lead.id }}', '{{ lead.source_url }}', this)"

                                class="btn-indigo px-3.5 py-2 rounded-lg text-xs font-bold shadow-sm">

                            ⚡ Copy Proposal & Open Job ↗

                        </button>



                        <form action="/autofill-one/{{ lead.id }}" method="POST" onsubmit="this.querySelector('button').innerText='🤖 Filling...';">

                            <button type="submit" class="btn-emerald px-3.5 py-2 rounded-lg text-xs font-semibold shadow-sm">

                                {% if lead.form_autofilled %}

                                    🤖 Re-Submit Form

                                {% else %}

                                    🤖 Auto-Fill Form

                                {% endif %}

                            </button>

                        </form>



                        {% if not lead.replied and lead.sequence_step < 3 and '@' in lead.contact_email %}

                        <form action="/send-step/{{ lead.id }}" method="POST">

                            <button type="submit" class="btn-gold px-3.5 py-2 rounded-lg text-xs font-semibold shadow-sm">

                                {% if lead.sequence_step == 0 %}

                                    🚀 Send Step 1 Email

                                {% else %}

                                    ⏭️ Send Step {{ lead.sequence_step + 1 }}/3

                                {% endif %}

                            </button>

                        </form>

                        {% endif %}

                    </div>

                </div>



                <!-- Freelance Proposal & Quick DM Box -->

                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-4">

                    <div class="lg:col-span-2 bg-indigo-50/60 p-3.5 rounded-lg border border-indigo-200">

                        <div class="flex items-center justify-between mb-1.5">

                            <span class="text-[11px] font-bold uppercase tracking-wider text-indigo-950">

                                📋 Tailored Upwork / Contra / Casting Proposal (Portfolio in Line 1 + 2 Custom Hooks)

                            </span>

                            <button type="button" onclick="copyTextOnly('prop-{{ lead.id }}', this)"

                                    class="text-[11px] px-2.5 py-0.5 rounded bg-indigo-900 text-white font-semibold">

                                📋 Copy Proposal

                            </button>

                        </div>

                        <div id="prop-{{ lead.id }}" class="text-xs text-[#2C2523] whitespace-pre-wrap leading-relaxed font-sans">{{ lead.freelance_proposal }}</div>

                    </div>



                    <div class="bg-[#FAF7F2] p-3.5 rounded-lg border border-[#E6DEC8] flex flex-col justify-between">

                        <div>

                            <div class="flex items-center justify-between mb-1.5">

                                <span class="text-[11px] font-bold uppercase tracking-wider text-[#3D2E24]">

                                    💬 Short DM / Casting Note (45 Words)

                                </span>

                                <button type="button" onclick="copyTextOnly('dm-{{ lead.id }}', this)"

                                        class="text-[11px] px-2 py-0.5 rounded gold-badge font-semibold">

                                    📋 Copy DM

                                </button>

                            </div>

                            <div id="dm-{{ lead.id }}" class="text-xs text-[#2C2523] whitespace-pre-wrap leading-relaxed">{{ lead.short_dm_pitch }}</div>

                        </div>

                        <div class="mt-3 pt-2 border-t border-[#E6DEC8] text-[11px] text-[#6E6259]">

                            <strong>Brief Snippet:</strong> "{{ lead.raw_snippet[:140] }}..."

                        </div>

                    </div>

                </div>



                <!-- Collapsible 3-Step Email Sequence Preview -->

                <details class="pt-3 mt-3 border-t border-[#F0EAE1]">

                    <summary class="text-xs font-semibold text-[#6E6259] cursor-pointer hover:text-[#261C15]">

                        📧 View 3-Step Automated Cold Email Sequence (Subject: {{ lead.email_subject }}) ▾

                    </summary>

                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-3">

                        <div class="bg-[#FAF7F2] p-3.5 rounded-lg border border-[#E6DEC8]">

                            <p class="text-[11px] font-bold uppercase text-[#3D2E24] mb-1">Step 1 (Day 0) • {{ lead.email_subject }}</p>

                            <div class="text-xs text-[#2C2523] whitespace-pre-wrap leading-relaxed">{{ lead.ai_pitch }}</div>

                        </div>

                        <div class="bg-[#FAF7F2] p-3.5 rounded-lg border border-[#E6DEC8]">

                            <p class="text-[11px] font-bold uppercase text-[#3D2E24] mb-1">Step 2 (+3 Days) • Hook Drop</p>

                            <div class="text-xs text-[#2C2523] whitespace-pre-wrap leading-relaxed">{{ lead.followup_1_body }}</div>

                        </div>

                        <div class="bg-[#FAF7F2] p-3.5 rounded-lg border border-[#E6DEC8]">

                            <p class="text-[11px] font-bold uppercase text-[#3D2E24] mb-1">Step 3 (+7 Days) • Break-Up</p>

                            <div class="text-xs text-[#2C2523] whitespace-pre-wrap leading-relaxed">{{ lead.followup_2_body }}</div>

                        </div>

                    </div>

                </details>

            </div>

            {% endfor %}

        </div>

    </div>

</body>

</html>

"""





@app.route("/")

def index():

    flash_msg = request.args.get("msg", "")

    current_region = request.args.get("region", "All Regions")



    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        all_rows = [dict(r) for r in conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()]



    if current_region != "All Regions":

        filtered_rows = [r for r in all_rows if (r.get("region") or "Global") == current_region]

    else:

        filtered_rows = all_rows



    ready_c = sum(1 for r in all_rows if r["sequence_step"] == 0 and not r["replied"] and "@" in (r["contact_email"] or ""))

    missing_email_c = sum(1 for r in all_rows if "@" not in (r["contact_email"] or ""))

    autofilled_c = sum(1 for r in all_rows if r.get("form_autofilled") == 1)

    applied_c = sum(1 for r in all_rows if r.get("proposal_applied") == 1)

    freelance_c = sum(1 for r in all_rows if (r.get("region") or "") == "Freelance & Job Boards")

    unfilled_form_c = sum(1 for r in all_rows if r.get("form_autofilled") == 0)

    active_seq = sum(1 for r in all_rows if r["sequence_step"] in (1, 2) and not r["replied"] and "Bounced" not in (r.get("status") or ""))



    return render_template_string(

        DASHBOARD_HTML,

        leads=filtered_rows,

        total_count=len(all_rows),

        ready_count=ready_c,

        missing_email_count=missing_email_c,

        autofilled_count=autofilled_c,

        applied_count=applied_c,

        freelance_count=freelance_c,

        unfilled_form_count=unfilled_form_c,

        active_seq_count=active_seq,

        sends_today=get_today_send_count(),

        daily_limit=DAILY_SEND_LIMIT,

        smtp_ok=bool(SMTP_EMAIL and SMTP_APP_PASSWORD),

        auto_pilot=AUTO_PILOT_ENABLED,

        tg_channels=get_tracked_channels(),

        profile=get_creator_profile(),

        current_region=current_region,

        flash_msg=flash_msg,

    )





@app.route("/sanitize-emails", methods=["POST"])

def trigger_sanitize_emails():

    cleaned = sanitize_corrupted_emails_in_db()

    replies, bounces = check_imap_for_replies_and_bounces()

    return redirect(

        url_for(

            "index",

            msg=f"Email Sanitizer & MX Check complete: Removed/repaired {cleaned} invalid emails (like 'up@...') and halted {bounces} bounced threads!",

        )

    )





@app.route("/mark-applied/<int:lead_id>", methods=["POST"])

def mark_proposal_applied(lead_id: int):

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(

            "UPDATE leads SET proposal_applied = 1, status = CASE WHEN status = 'New' THEN 'Proposal Applied ✅' ELSE status END WHERE id = ?",

            (lead_id,),

        )

        conn.commit()

    return jsonify({"ok": True})





@app.route("/scan", methods=["POST"])

def trigger_scan():

    res = run_discovery_pipeline(deep_mode=False)

    return redirect(url_for("index", msg=f"Quick scan complete: {res['scanned']} signals checked, {res['added']} new leads saved, {res['backfilled']} MX-verified emails enriched."))





@app.route("/deep-scan", methods=["POST"])

def trigger_deep_scan():

    res = run_discovery_pipeline(deep_mode=True)

    return redirect(url_for("index", msg=f"Hyper-Scan complete: {res['scanned']} multi-platform signals analyzed, {res['added']} new leads added, {res['backfilled']} MX-verified emails enriched!"))





@app.route("/scan-telegram", methods=["POST"])

def trigger_telegram_scan():

    stats = scrape_telegram_channels_and_search()

    return redirect(

        url_for(

            "index",

            msg=(

                f"Telegram scan complete: Scanned {stats['channels_scanned']} channels "

                f"(+{stats['new_channels_found']} new channels auto-discovered), "

                f"found {stats['briefs_found']} briefs, saved {stats['saved']} new leads."

            ),

        )

    )





@app.route("/autofill-one/<int:lead_id>", methods=["POST"])

def trigger_autofill_one(lead_id: int):

    ok, msg = autofill_lead_form(lead_id)

    prefix = "✅ Form Auto-Filled!" if ok else "ℹ️ Auto-Fill Note:"

    return redirect(url_for("index", msg=f"{prefix} (Lead #{lead_id}) {msg}"))





@app.route("/bulk-autofill", methods=["POST"])

def trigger_bulk_autofill():

    stats = bulk_autofill_all_forms(limit=30)

    return redirect(

        url_for(

            "index",

            msg=f"Bulk Form Auto-Filler finished: Attempted {stats['attempted']} forms, auto-submitted {stats['filled']} forms directly!",

        )

    )





@app.route("/save-profile", methods=["POST"])

def save_profile_route():

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("""

            UPDATE creator_profile

            SET full_name = ?, email = ?, portfolio_url = ?, phone = ?,

                tiktok_handle = ?, instagram_handle = ?, country = ?,

                standard_rate = ?, bio_pitch = ?

            WHERE id = 1

        """, (

            request.form.get("full_name", "").strip(),

            request.form.get("email", "").strip(),

            request.form.get("portfolio_url", "").strip(),

            request.form.get("phone", "").strip(),

            request.form.get("tiktok_handle", "").strip(),

            request.form.get("instagram_handle", "").strip(),

            request.form.get("country", "").strip(),

            request.form.get("standard_rate", "").strip(),

            request.form.get("bio_pitch", "").strip(),

        ))

        conn.execute("UPDATE leads SET freelance_proposal = ''")

        conn.commit()

    backfill_freelance_proposals()

    return redirect(url_for("index", msg="Saved your Creator Profile & updated all Upwork/Contra/Backstage proposals!"))





@app.route("/enrich-emails", methods=["POST"])

def trigger_enrich_emails():

    found = backfill_missing_emails()

    return redirect(url_for("index", msg=f"Free Deep Email Enrichment complete: Found & MX-verified {found} new emails!"))





@app.route("/send-ready", methods=["POST"])

def trigger_send_ready():

    sent = send_all_ready_leads()

    return redirect(url_for("index", msg=f"Batch send complete: Launched Step 1 for {sent} MX-verified leads."))





@app.route("/instant-drop", methods=["POST"])

def instant_lead_drop():

    url = request.form.get("source_url", "").strip()

    direct_email = request.form.get("direct_email", "").strip()

    item = {

        "platform": "Instant Lead Drop",

        "niche": "Direct Application",

        "region": infer_region("", url),

        "title": f"Portal ({extract_clean_domain(url) or 'Creator Brief'})",

        "snippet": f"Creator sign up application portal: {url}",

        "source_url": url,

        "brand_domain": extract_clean_domain(url),

    }

    saved = process_and_save_signal(item, forced_email=direct_email)

    return redirect(url_for("index", msg="Instant Lead analyzed, proposal generated, and added!" if saved else "Lead URL already exists in database."))





@app.route("/add-tg", methods=["POST"])

def add_tg_channel():

    handle = request.form.get("handle", "").strip().lstrip("@").split("/")[-1]

    if handle:

        with sqlite3.connect(DB_PATH) as conn:

            conn.execute("INSERT OR IGNORE INTO telegram_channels (handle) VALUES (?)", (handle,))

            conn.commit()

    stats = scrape_telegram_channels_and_search()

    return redirect(url_for("index", msg=f"Added @{handle} & scanned Telegram: found {stats['briefs_found']} briefs, saved {stats['saved']} new leads."))





@app.route("/remove-tg/<string:handle>", methods=["POST"])

def remove_tg_channel(handle: str):

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("DELETE FROM telegram_channels WHERE handle = ?", (handle,))

        conn.commit()

    return redirect(url_for("index", msg=f"Removed @{handle} from tracked Telegram channels."))





@app.route("/export")

def export_csv():

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()



    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow(["ID", "Brand", "Platform", "Region", "Email", "Form Auto-Filled", "Proposal Applied", "Source URL", "Status", "Sequence Step"])

    for r in rows:

        writer.writerow([r["id"], r["brand_name"], r["platform"], r["region"], r["contact_email"], r["form_autofilled"], r["proposal_applied"], r["source_url"], r["status"], r["sequence_step"]])



    return Response(

        output.getvalue(),

        mimetype="text/csv",

        headers={"Content-Disposition": "attachment;filename=ugc_leads_export.csv"},

    )





@app.route("/send-step/<int:lead_id>", methods=["POST"])

def trigger_send_step(lead_id: int):

    ok, message = send_sequence_step(lead_id)

    return redirect(url_for("index", msg=message))





@app.route("/run-outreach-queue", methods=["POST"])

def trigger_outreach_queue():

    stats = process_scheduled_outreach_queue()

    return redirect(

        url_for(

            "index",

            msg=f"Outreach sync finished: {stats['replies_detected']} replies detected, {stats['bounces_halted']} bounced threads halted, {stats['followups_sent']} due follow-ups sent.",

        )

    )





@app.route("/update-email/<int:lead_id>", methods=["POST"])

def update_lead_email(lead_id: int):

    new_email = request.form.get("contact_email", "").strip().lower()

    if not is_valid_deliverable_email(new_email, check_mx=True):

        return redirect(url_for("index", msg=f"⚠️ Blocked '{new_email}': Invalid format or domain has no MX mail servers."))

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("UPDATE leads SET contact_email = ?, decision_maker = 'Verified MX Contact' WHERE id = ?", (new_email, lead_id))

        conn.commit()

    if AUTO_PILOT_ENABLED:

        ok, send_msg = send_sequence_step(lead_id)

        return redirect(url_for("index", msg=f"Verified MX for {new_email} & Auto-Pilot triggered: {send_msg}"))

    return redirect(url_for("index", msg=f"Updated & MX-verified contact email for Lead #{lead_id} to {new_email}"))





if __name__ == "__main__":

    init_db()

    # 1. Immediately purge/repair false-positive emails like 'up@scoutmadeugc.com'

    sanitize_corrupted_emails_in_db()

    # 2. Check Gmail for any past bounces and halt their follow-ups

    check_imap_for_replies_and_bounces()

    # 3. Backfill proposals and verified MX emails

    backfill_freelance_proposals()

    backfill_missing_emails()



    scheduler = BackgroundScheduler()

    scheduler.add_job(lambda: run_discovery_pipeline(deep_mode=True), "interval", hours=3)

    scheduler.add_job(scrape_telegram_channels_and_search, "interval", hours=2)

    scheduler.add_job(lambda: bulk_autofill_all_forms(limit=20), "interval", hours=4)

    scheduler.add_job(process_scheduled_outreach_queue, "interval", minutes=45)

    scheduler.start()



    logger.info("UGC Omni-Platform Hunter + MX Email Verifier running on http://127.0.0.1:5000")

    app.run(host="0.0.0.0", port=5000, debug=False)