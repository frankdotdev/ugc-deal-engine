# 🎬 UGC Deal Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![CI Status](https://img.shields.io/badge/CI-passing-brightgreen.svg)](https://github.com/frankdotdev/ugc-deal-engine/actions)

An open-source, autonomous deal engine for **User Generated Content (UGC) creators, creative strategists, and performance ad agencies**.

**UGC Deal Engine** continuously tracks brands actively seeking creator talent or heavily spending on TikTok and Meta ads, scores and qualifies their buyer intent with Google Gemini AI, enriches contact details with Hunter.io, and manages a compliant, threaded 3-step outreach sequence that **automatically stops the moment a recipient replies, opts out, or bounces**.

---

## 📌 Table of Contents

- [Why UGC Deal Engine?](#-why-ugc-deal-engine)
- [How It Works (Architecture)](#-how-it-works-architecture)
- [Key Features](#-key-features)
- [Directory Layout](#-directory-layout)
- [Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Local Setup (macOS / Linux / Windows)](#local-setup)
  - [Docker & Production Deployment](#docker--production-deployment)
- [Environment Configuration Guide](#-environment-configuration-guide)
- [How to Obtain API Keys & Credentials](#-how-to-obtain-api-keys--credentials)
- [CLI Reference](#-cli-reference)
- [Safety & Compliance Rules](#-safety--compliance-rules)
- [Contributing](#-contributing)
- [Author & Credits](#-author--credits)
- [License & Disclaimer](#-license--disclaimer)

---

## 💡 Why UGC Deal Engine?

Cold DMing hundreds of random brands on Instagram or scouring job boards wastes hours every week. Existing cold outreach software is generic, expensive, and sends unpersonalized spam that burns domain reputations.

**UGC Deal Engine** was engineered specifically for creator monetization:
1. **High Buyer Intent Discovery:** Scrapes real-time signals where brands *ask* for creators (Twitter/X, LinkedIn posts, Notion briefs, Google Forms creator applications) or finds active ad spenders on TikTok & Meta Ad Libraries.
2. **AI Creative Strategist:** Uses Google Gemini to examine what the brand is advertising, draft two custom 3-second hook scripts tailored to their product, and write concise, value-first emails without generic fluff.
3. **Automated Safety Sentinel:** Regularly polls IMAP inbox before sending any follow-up. If a prospect replies "no thanks" or unsubscribes, the engine instantly suppresses their email and stops all follow-ups.
4. **100% Self-Hosted & Free:** No recurring monthly SaaS fees. Built on SQLite with WAL mode, Flask, and APScheduler.

---

## 🏗️ How It Works (Architecture)

```
            ┌────────────── Web Process (Flask / Gunicorn) ─────────────┐        ┌───────────── Worker Process ────────────┐
 You ──────▶│ Dashboard: review leads, edit hooks, approve, trigger send │        │ - Discovery scanner: every N hours      │
            │ Queues jobs to SQLite ────────────────────────────┐       │        │ - IMAP Inbox + Follow-up: every 30 min  │
            └───────────────────────────────────────────────────┼───────┘        │ - Dashboard job processor: every 15 sec │
                                                                ▼                │                                         │
                                                      SQLite Database (WAL) ◀───▶│                                         │
                                                                                 └────────────────────┬────────────────────┘
        Serper.dev (Google X-Ray)   Apify (Ad Libraries)   Google Gemini   Hunter.io                  │ SMTP / IMAP (Gmail)
```

The system operates using a decoupled **Web Dashboard** and **Background Worker**:
- **Web Dashboard:** Clean, lightweight user interface to review discovered brands, read AI-generated hooks, edit email templates, manually trigger sends, or update lead pipeline statuses (`New`, `Replied`, `Negotiating`, `Closed Won`, `Archived`).
- **Worker Scheduler:** Runs autonomous background tasks. Sends are claimed atomically in SQLite (`claim_step`), eliminating race conditions and ensuring that no recipient ever receives duplicate outreach.

---

## ✨ Key Features

- **Multi-Source Discovery:**
  - **Google X-Ray via Serper.dev:** Targets high-intent keywords across X (Twitter), LinkedIn Posts, Google Forms applications, Notion briefs, TikTok, and brand creator application pages.
  - **Ad Library Scraper via Apify:** Identifies brands with active ad spend in target niches (`skincare`, `AI SaaS`, `fitness`, `pet supplements`, etc.) on TikTok & Meta.
- **AI Qualification & Pitch Generation (Gemini 2.5 Flash):**
  - Rejects creator self-promotions, job-seekers, and spam.
  - Scores urgency and intent (1-100).
  - Produces two tailored 3-second video hook concepts.
  - Drafts an ultra-short (under 75 words) 3-step value sequence.
  - Fallback rule-based engine activates if Gemini API is disabled.
- **Decision-Maker Email Enrichment:**
  - Extracts direct contact emails from post snippets.
  - Queries **Hunter.io** for verified brand emails (prioritizing Growth, Marketing, Founder, Social, and Creative roles).
  - Fallback scraping on public brand domains (`/contact`, `/partnerships`).
- **Compliant Outreach Sentinel:**
  - Threaded follow-ups with proper RFC headers (`Message-ID`, `In-Reply-To`, `References`).
  - CAN-SPAM / GDPR / UK PECR compliant footer with sender name, portfolio link, postal address, and opt-out instructions.
  - `List-Unsubscribe` mailto header included on every email.
  - IMAP listener detects replies, bounces (mailer-daemon/postmaster), and opt-outs (`"no thanks"`, `"unsubscribe"`, `"remove me"`).
  - Built-in suppression list to permanently prevent contacting opted-out addresses.
- **Operational Guardrails:**
  - Daily send volume cap (`DAILY_SEND_LIMIT`).
  - Business hours UTC send window (`SEND_WINDOW_UTC`).
  - Randomized pause between dispatches (`SEND_JITTER_SECONDS`).
  - `DRY_RUN` mode enabled by default (all actions simulated until you intentionally go live).

---

## 📂 Directory Layout

```
ugc-deal-engine/
├── .github/workflows/
│   └── ci.yml                # Automated test matrix (Python 3.10 & 3.12)
├── src/ugc_engine/
│   ├── ai.py                 # Gemini prompt qualification, sequence generator & fallback
│   ├── cli.py                # Command-line interface (`ugc-engine`)
│   ├── clock.py              # Centralized UTC clock helpers
│   ├── config.py             # Typed settings, validation & production safety checks
│   ├── db.py                 # SQLite connection & user_version schema migrations
│   ├── discovery.py          # Pipeline: scrape -> qualify -> enrich -> persist
│   ├── enrichment.py         # Regex email extractor, Hunter.io client & domain resolver
│   ├── http.py               # Resilient HTTP session with retries & custom User-Agent
│   ├── inbox.py              # IMAP email classification (replies, opt-outs, bounces)
│   ├── logging_setup.py      # Standardized logging configuration
│   ├── mailer.py             # MIME message builder, SMTP transport & safety rules
│   ├── outreach.py           # Scheduled dispatcher (inbox check -> follow-ups)
│   ├── repository.py         # Data persistence layer & atomic transactions
│   ├── scheduler.py          # APScheduler background worker daemon
│   ├── scrapers/
│   │   ├── ads.py            # Apify TikTok & Meta ad library scrapers
│   │   └── xray.py           # Serper.dev Google X-Ray search scraper
│   └── web/
│       ├── factory.py        # Flask application factory & reverse-proxy integration
│       ├── security.py       # Basic auth, brute-force throttle, CSRF & CSP headers
│       ├── static/           # Styling & UI assets
│       ├── templates/        # Jinja2 dashboard templates
│       └── views.py          # Dashboard routes, CSV export & manual actions
├── tests/                    # Comprehensive Pytest test suite
├── .env.example              # Template environment variables
├── docker-compose.yml        # Multi-container production deployment
├── Dockerfile                # Production container definition
├── Makefile                  # Helper commands
├── pyproject.toml            # Project metadata & dependencies
└── LICENSE                   # MIT License
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10, 3.11, or 3.12
- Git
- (Optional) Docker & Docker Compose

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/frankdotdev/ugc-deal-engine.git
   cd ugc-deal-engine
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   # Using Make:
   make install

   # Or manually:
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev,prod]"
   ```

3. **Configure your environment:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your editor of choice (see [Environment Configuration Guide](#-environment-configuration-guide)).

4. **Verify your configuration:**
   ```bash
   ugc-engine check-config
   ```

5. **Populate demo data (optional):**
   ```bash
   ugc-engine seed-demo
   ```

6. **Start everything with one command:**
   ```bash
   make start
   # Or: ugc-engine start (alias: ugc-engine run)
   ```
   Both the **Web Dashboard** and the **Worker Scheduler** run concurrently in your single terminal!
   Open `http://127.0.0.1:5000` in your browser. (Login username: `admin`, password: see terminal output or your `DASHBOARD_PASSWORD`).

   *(Optional)* If you prefer running them in separate processes:
   - Terminal 1: `ugc-engine web`
   - Terminal 2: `ugc-engine worker`

### Docker & Production Deployment

For continuous server execution:

```bash
# 1. Prepare your .env configuration
cp .env.example .env
nano .env

# 2. Build and run via Docker Compose
docker compose up -d --build

# 3. View logs
docker compose logs -f
```

The web dashboard is exposed at `http://127.0.0.1:8000`. Place a reverse proxy such as Caddy or Nginx in front of it to handle TLS termination, and configure `COOKIE_SECURE=true` and `TRUST_PROXY=true` in `.env`.

---

## ⚙️ Environment Configuration Guide

| Variable | Default | Required? | Description |
|---|---|---|---|
| **Core & Storage** | | | |
| `APP_ENV` | `production` | Yes | `development` or `production`. In production, strict security validations are enforced. |
| `DB_PATH` | `data/ugc_engine.db` | Yes | Path to SQLite database file. Automatically managed with WAL mode. |
| `LOG_LEVEL` | `INFO` | No | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| **Web Dashboard** | | | |
| `DASHBOARD_PASSWORD` | *(auto in dev)* | In Prod (12+ chars) | Password for `admin` dashboard login. Required in production. |
| `SECRET_KEY` | *(derived)* | No | Flask session secret key. Auto-derived from dashboard password if blank. |
| `HOST` | `127.0.0.1` | No | Web bind address (`0.0.0.0` in Docker). |
| `PORT` | `5000` | No | Web server port (`8000` in Docker). |
| `COOKIE_SECURE` | `false` | When HTTPS | Enforces `Secure` flag on session cookies when served behind HTTPS. |
| `TRUST_PROXY` | `false` | When behind proxy | Enables Werkzeug `ProxyFix` when behind Caddy/Nginx/Traefik. |
| **Discovery & Scrapers** | | | |
| `SERPER_API_KEY` | `""` | Recommended | Serper.dev API key for Google X-Ray searches across social platforms and briefs. |
| `APIFY_API_TOKEN` | `""` | Optional | Apify token for TikTok and Meta Ad Library scraping actors. |
| `APIFY_ACTOR_TIKTOK` | `muhammadafzal/tiktok-ads-library-scraper` | Optional | Actor ID for TikTok Ad Library scraper. |
| `APIFY_ACTOR_META` | `data_ops_main/meta-ads` | Optional | Actor ID for Meta Ad Library scraper. |
| `APIFY_NICHES_PER_RUN` | `2` | No | Number of niches sampled from `TARGET_NICHES` during each ad library run. |
| `TARGET_NICHES` | `skincare,matcha,AI SaaS,fitness app,pet supplements` | No | Comma-separated niches to discover and target. |
| `DISCOVERY_HOURS` | `6` | No | Interval (in hours) between scheduled automated discovery scans. |
| `MIN_SCORE_SAVE` | `50` | No | Minimum AI qualification score (1-100) required to save a lead to database. |
| **AI Qualification** | | | |
| `GEMINI_API_KEY` | `""` | Recommended | Google Gemini API key to score leads and write personalized hooks & sequences. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | No | Gemini model name (default: `gemini-2.5-flash`). |
| **Enrichment** | | | |
| `HUNTER_API_KEY` | `""` | Optional | Hunter.io API key for finding verified marketing/founder decision-maker emails. |
| **Sender Identity (CAN-SPAM)** | | | |
| `SMTP_SENDER_NAME` | `"Your Name"` | In Live Mode | Your name or creator brand name appearing in email headers and signatures. |
| `PORTFOLIO_URL` | `"https://your-portfolio-link.com"` | In Live Mode | Public portfolio link showcasing your UGC videos. |
| `SENDER_OFFER` | `"an independent UGC creator..."` | No | Brief explanation of your offer used by Gemini to generate relevant pitch angles. |
| `SENDER_POSTAL_ADDRESS` | `""` | In Live Mode | Real physical address or P.O. Box (required by commercial email law). |
| **Email Transport (Gmail)** | | | |
| `SMTP_EMAIL` | `""` | In Live Mode | Your sending Gmail or Google Workspace address. |
| `SMTP_APP_PASSWORD` | `""` | In Live Mode | 16-character Google App Password (not your personal account password). |
| `SMTP_HOST` | `smtp.gmail.com` | No | SMTP server hostname. |
| `SMTP_PORT` | `465` | No | SMTP SSL port. |
| `IMAP_HOST` | `imap.gmail.com` | No | IMAP server hostname. |
| `IMAP_PORT` | `993` | No | IMAP SSL port. |
| **Outreach Controls** | | | |
| `DRY_RUN` | `true` | Yes | **Safety default: `true`**. When `true`, emails are simulated and logged, not sent. |
| `DAILY_SEND_LIMIT` | `20` | No | Maximum automated email dispatches allowed per calendar day. |
| `FOLLOWUP_DELAYS_DAYS` | `3,7` | No | Sequence delays: step 2 sent after 3 days; step 3 sent 7 days later (day 10). |
| `AUTO_SEND_FIRST` | `false` | No | `false` requires manual approval on the dashboard for Step 1. `true` sends automatically. |
| `AUTO_SEND_MIN_SCORE` | `75` | No | Minimum score required when `AUTO_SEND_FIRST=true`. |
| `SEND_WINDOW_UTC` | `08-18` | No | Permitted UTC sending hours (Mon-Fri only). |
| `SEND_JITTER_SECONDS` | `20-75` | No | Randomized delay in seconds between consecutive emails to protect reputation. |
| `QUEUE_MINUTES` | `30` | No | Interval (in minutes) for worker inbox checks and due follow-up processing. |

---

### 🧩 Modular & Independent Architecture

Every external API integration in UGC Deal Engine is completely decoupled and optional. The engine will run smoothly and gracefully adapt regardless of which keys you configure:

- **No `SERPER_API_KEY`:** Google X-Ray searches are skipped; ad library and demo leads continue to work.
- **No `APIFY_API_TOKEN`:** TikTok/Meta Ad Library scrapers are skipped; Serper X-Ray leads continue to work.
- **No `GEMINI_API_KEY` (or if Gemini quota is exceeded):** Automatically falls back to the built-in rule-based qualifier and sequence generator.
- **No `HUNTER_API_KEY`:** Decision-maker lookup falls back to direct post-snippet parsing and brand website crawling.
- **No `SMTP_EMAIL` / `SMTP_APP_PASSWORD`:** Outreach runs in safe simulation mode (`[SIMULATED]`), allowing you to test sequences and dashboard interactions without sending real messages.

---

## 🔑 How to Obtain API Keys & Credentials

### 1. Google Gemini API Key (`GEMINI_API_KEY`)
*Powers AI lead qualification, intent scoring, and hook script generation.*
1. Visit [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your Google account.
3. Click **Get API key** (or **Create API key**).
4. Select or create a Google Cloud project and copy your new API key.
5. Paste into `.env`:
   ```env
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-2.5-flash
   ```

### 2. Serper.dev API Key (`SERPER_API_KEY`)
*Powers Google X-Ray searches across X/Twitter, LinkedIn, Google Forms briefs, Notion, and TikTok.*
1. Go to [serper.dev](https://serper.dev/) and sign up.
2. Serper provides 2,500 free Google searches upon sign-up.
3. Go to your **Dashboard** and copy the **API Key**.
4. Paste into `.env`:
   ```env
   SERPER_API_KEY=your_serper_api_key_here
   ```

### 3. Apify API Token (`APIFY_API_TOKEN`)
*Extracts active advertisers from TikTok & Meta Ad Libraries.*
1. Go to [apify.com](https://apify.com/) and register a free account.
2. In the left navigation, go to **Settings** > **Integrations** (or visit `console.apify.com/account/integrations`).
3. Click **Add token** or copy your **Personal API token**.
4. Paste into `.env`:
   ```env
   APIFY_API_TOKEN=apify_api_...
   ```
   *(Optional)* Check the Apify Store for actors `muhammadafzal/tiktok-ads-library-scraper` and `data_ops_main/meta-ads` to test or customize search parameters.

### 4. Hunter.io API Key (`HUNTER_API_KEY`)
*Finds verified email addresses for growth and marketing decision-makers at brand domains.*
1. Go to [hunter.io](https://hunter.io/) and create an account (free plan includes 25 searches/month).
2. Navigate to **API** in the user menu (or visit `hunter.io/api_keys`).
3. Copy your API Key.
4. Paste into `.env`:
   ```env
   HUNTER_API_KEY=your_hunter_api_key_here
   ```

### 5. Gmail SMTP & IMAP Credentials (`SMTP_EMAIL` & `SMTP_APP_PASSWORD`)
*Sends outreach emails and monitors inbox for replies and unsubscribes.*
> ⚠️ **Best Practice:** Use a dedicated Google Workspace or secondary Gmail account—never your primary personal inbox.
1. Sign in to your sending Google Account at [myaccount.google.com](https://myaccount.google.com/).
2. Select **Security** from the left navigation.
3. Under *How you sign in to Google*, ensure **2-Step Verification** is turned **ON**.
4. Search for or navigate to **App passwords** (`myaccount.google.com/apppasswords`).
5. Enter a name (e.g. `UGC Deal Engine`) and click **Create**.
6. Google will display a 16-character code (e.g. `abcd efgh ijkl mnop`).
7. Paste into `.env` (spaces are automatically stripped):
   ```env
   SMTP_EMAIL=your-sending-address@gmail.com
   SMTP_APP_PASSWORD=abcdefghijklmnop
   ```

### 6. Dashboard Password (`DASHBOARD_PASSWORD`)
*Protects the web dashboard against unauthorized access.*
- Choose any secure password of 12 or more characters:
  ```env
  DASHBOARD_PASSWORD=YourSuperSecurePassword123!
  ```
- In development mode (`APP_ENV=development`), if left blank, a random password is generated and printed in your terminal upon startup.

---

## 💻 CLI Reference

The `ugc-engine` CLI allows direct control over the engine:

```bash
# Run everything at once (Web Dashboard + Worker Daemon together)
ugc-engine start    # or: ugc-engine run

# Validate your .env settings against production rules
ugc-engine check-config

# Run the web dashboard development server separately
ugc-engine web

# Run the background worker daemon separately (scans, inbox checks, follow-ups)
ugc-engine worker

# Execute an immediate discovery scan right now
ugc-engine scan

# Execute an immediate inbox check & due follow-up pass right now
ugc-engine queue

# Seed the database with demo leads (flagged, never sent in live mode)
ugc-engine seed-demo

# Perform a safe, consistent live SQLite backup
ugc-engine backup backups/ugc_backup.db
```

---

## 🛡️ Safety & Compliance Rules

UGC Deal Engine comes with built-in protections:

1. **Simulation Default:** `DRY_RUN=true` ensures no real email can leave the system until you review generated leads and explicitly toggle it to `false`.
2. **Demo Lead Protection:** Demo leads created via `seed-demo` have `is_demo=1`. The mailer strictly refuses to send to demo records even if live mode is activated.
3. **Automatic Sequence Termination:**
   - Any reply stops the sequence immediately (`Replied` status).
   - Any negative phrase (`"unsubscribe"`, `"remove me"`, `"no thanks"`, `"not interested"`) moves the lead to `Unsubscribed` and saves the email to the `suppression` table.
   - Any bounce notification from `mailer-daemon` or `postmaster` marks the lead as `Bounced` and suppresses the address.
   - Automated out-of-office / auto-replies are ignored so the sequence remains cleanly intact.
4. **Single-Contact Deduplication:** The engine checks historical send logs across all leads. If an address was previously contacted under another record, it is blocked from receiving duplicate outreach.
5. **Rate & Schedule Throttling:**
   - `DAILY_SEND_LIMIT` strictly caps daily outgoing volume.
   - `SEND_WINDOW_UTC` limits automated sends to working business hours (Monday through Friday).
   - `SEND_JITTER_SECONDS` inserts random delays (20–75s) between emails to prevent burst spikes.
6. **Commercial Email Compliance (CAN-SPAM / PECR / GDPR):**
   - Requires real sender name (`SMTP_SENDER_NAME`) and physical address (`SENDER_POSTAL_ADDRESS`).
   - Every email body concludes with a clear opt-out sentence.
   - Every message includes an RFC-compliant `List-Unsubscribe` mailto header.
7. **Dashboard Security:**
   - HTTP Basic Auth with IP-based brute-force throttling (locks out after 10 failed attempts per 10-minute window).
   - CSRF protection across all state-changing `POST` endpoints.
   - Secure HTTP headers (`CSP`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`).
   - CSV export sanitizes leading `=`, `+`, `-`, and `@` characters to neutralize CSV formula injection attacks.

---

## 🧪 Development & Testing

Run unit and integration tests using pytest:

```bash
# Run tests
make test
# Or: pytest

# Run linter
make lint
# Or: ruff check src tests
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository** on GitHub.
2. **Create a feature branch:**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes** and add appropriate tests in `tests/`.
4. **Verify tests and linting pass:**
   ```bash
   make test
   make lint
   ```
5. **Commit your changes with clear messages:**
   ```bash
   git commit -m "feat: add support for custom webhook alerts"
   ```
6. **Push to the branch:**
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open a Pull Request** describing your changes.

---

## 👤 Author & Credits

Built with ❤️ by **[Frank Oge](https://frankoge.com)** of **[Hackverse Technologies](https://hackversetechnologies.vercel.app)**.

---

## ⚖️ License & Disclaimer

This project is licensed under the **[MIT License](LICENSE)**.

### Legal Disclaimer
*UGC Deal Engine provides the mechanical tooling for lead discovery and compliant email sending (suppression lists, opt-out headers, and address requirements). However, email marketing regulations (including the US CAN-SPAM Act, Canadian CASL, UK PECR, and EU GDPR) differ by region and context. You are solely responsible for ensuring your outreach practices comply with all local and international laws applicable to you and your recipients. This project is provided as-is without any warranties or guarantees of deal closure.*

---

<div align="center">
  <sub>Built by <a href="https://frankoge.com">Frank Oge</a> of <a href="https://hackversetechnologies.vercel.app">Hackverse Technologies</a></sub>
</div>
