"""Application settings, read from environment variables (and an optional .env file)."""
from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

PLACEHOLDER_SENDER = "Your Name"
PLACEHOLDER_PORTFOLIO = "https://your-portfolio-link.com"


class ConfigError(ValueError):
    """Raised when configuration is missing or unsafe."""


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool(name: str, default: bool = False) -> bool:
    return _env(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in _env(name, default).split(",") if x.strip())


def _range(name: str, default: str, lo: int, hi: int) -> tuple[int, int]:
    raw = _env(name, default)
    try:
        a, b = (int(x) for x in raw.split("-"))
    except ValueError as exc:
        raise ConfigError(f"{name} must look like '08-18', got {raw!r}") from exc
    if not (lo <= a <= b <= hi):
        raise ConfigError(f"{name} must satisfy {lo} <= start <= end <= {hi}")
    return a, b


@dataclass(frozen=True)
class Settings:
    env: str
    db_path: str
    log_level: str
    # web
    host: str
    port: int
    dashboard_password: str
    password_generated: bool
    secret_key: str
    cookie_secure: bool
    trust_proxy: bool
    # discovery
    serper_api_key: str
    apify_api_token: str
    apify_actor_tiktok: str
    apify_actor_meta: str
    apify_input_tiktok: str
    apify_input_meta: str
    gemini_api_key: str
    gemini_model: str
    hunter_api_key: str
    target_niches: tuple[str, ...]
    apify_niches_per_run: int
    discovery_hours: int
    min_score_save: int
    # sender identity
    sender_name: str
    sender_offer: str
    portfolio_url: str
    postal_address: str
    # email transport
    smtp_email: str
    smtp_app_password: str
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    # outreach behaviour
    dry_run: bool
    daily_send_limit: int
    followup_delays: tuple[int, int]
    auto_send_first: bool
    auto_send_min_score: int
    send_window_utc: tuple[int, int]
    send_jitter: tuple[int, int]
    queue_minutes: int

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def live_email(self) -> bool:
        return bool(self.smtp_email and self.smtp_app_password and not self.dry_run)

    def problems(self, role: str = "web") -> list[str]:
        """Return a list of blocking configuration problems for the given role ('web' or 'worker')."""
        out: list[str] = []
        if role == "web" and self.is_production and len(self.dashboard_password) < 12:
            out.append("DASHBOARD_PASSWORD must be set to 12+ characters when APP_ENV=production.")
        if not self.dry_run:
            if not (self.smtp_email and self.smtp_app_password):
                out.append("DRY_RUN=false needs SMTP_EMAIL and SMTP_APP_PASSWORD.")
            if not self.postal_address:
                out.append("DRY_RUN=false needs SENDER_POSTAL_ADDRESS (required in commercial email, e.g. CAN-SPAM).")
            if self.sender_name == PLACEHOLDER_SENDER:
                out.append("Set SMTP_SENDER_NAME to your real name/brand before sending.")
            if self.portfolio_url == PLACEHOLDER_PORTFOLIO:
                out.append("Set PORTFOLIO_URL to your real portfolio before sending.")
        return out

    def warnings(self) -> list[str]:
        out = []
        if not (self.serper_api_key or self.apify_api_token):
            out.append("No SERPER_API_KEY or APIFY_API_TOKEN set: discovery will find nothing.")
        if not self.gemini_api_key:
            out.append("No GEMINI_API_KEY: using keyword rules and generic templates (lower lead/email quality).")
        if not self.hunter_api_key:
            out.append("No HUNTER_API_KEY: contact lookup falls back to emails found on brand websites.")
        if self.dry_run:
            out.append("DRY_RUN=true: no real emails are sent.")
        return out


def load_settings() -> Settings:
    load_dotenv()
    env = _env("APP_ENV", "development").lower()
    password = _env("DASHBOARD_PASSWORD")
    generated = False
    if not password and env != "production":
        password, generated = secrets.token_urlsafe(10), True
    secret = _env("SECRET_KEY") or hashlib.sha256(f"ugc-engine|{password}".encode()).hexdigest()
    delays = tuple(int(x) for x in _csv("FOLLOWUP_DELAYS_DAYS", "3,7"))
    if len(delays) != 2 or min(delays) < 1:
        raise ConfigError("FOLLOWUP_DELAYS_DAYS must be two positive integers, e.g. '3,7'")
    return Settings(
        env=env,
        db_path=_env("DB_PATH", "data/ugc_engine.db"),
        log_level=_env("LOG_LEVEL", "INFO"),
        host=_env("HOST", "127.0.0.1"),
        port=_int("PORT", 5000),
        dashboard_password=password,
        password_generated=generated,
        secret_key=secret,
        cookie_secure=_bool("COOKIE_SECURE", False),
        trust_proxy=_bool("TRUST_PROXY", False),
        serper_api_key=_env("SERPER_API_KEY"),
        apify_api_token=_env("APIFY_API_TOKEN"),
        apify_actor_tiktok=_env("APIFY_ACTOR_TIKTOK", "muhammadafzal/tiktok-ads-library-scraper"),
        apify_actor_meta=_env("APIFY_ACTOR_META", "data_ops_main/meta-ads"),
        apify_input_tiktok=_env("APIFY_INPUT_TIKTOK", '{"searchMode": "keyword", "query": "{niche}", "maxResults": 25}'),
        apify_input_meta=_env(
            "APIFY_INPUT_META",
            '{"searchQuery": "{niche}", "country": "US", "activeStatus": "active", "maxResults": 30}',
        ),
        gemini_api_key=_env("GEMINI_API_KEY"),
        gemini_model=_env("GEMINI_MODEL", "gemini-2.5-flash"),
        hunter_api_key=_env("HUNTER_API_KEY"),
        target_niches=_csv("TARGET_NICHES", "skincare,matcha,AI SaaS,fitness app,pet supplements"),
        apify_niches_per_run=_int("APIFY_NICHES_PER_RUN", 2),
        discovery_hours=_int("DISCOVERY_HOURS", 6),
        min_score_save=_int("MIN_SCORE_SAVE", 50),
        sender_name=_env("SMTP_SENDER_NAME", PLACEHOLDER_SENDER),
        sender_offer=_env(
            "SENDER_OFFER", "an independent UGC creator who films native, vertical problem-solution video ads"
        ),
        portfolio_url=_env("PORTFOLIO_URL", PLACEHOLDER_PORTFOLIO),
        postal_address=_env("SENDER_POSTAL_ADDRESS"),
        smtp_email=_env("SMTP_EMAIL"),
        smtp_app_password=_env("SMTP_APP_PASSWORD").replace(" ", ""),
        smtp_host=_env("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=_int("SMTP_PORT", 465),
        imap_host=_env("IMAP_HOST", "imap.gmail.com"),
        imap_port=_int("IMAP_PORT", 993),
        dry_run=_bool("DRY_RUN", True),
        daily_send_limit=_int("DAILY_SEND_LIMIT", 20),
        followup_delays=(delays[0], delays[1]),
        auto_send_first=_bool("AUTO_SEND_FIRST", False),
        auto_send_min_score=_int("AUTO_SEND_MIN_SCORE", 75),
        send_window_utc=_range("SEND_WINDOW_UTC", "08-18", 0, 24),
        send_jitter=_range("SEND_JITTER_SECONDS", "20-75", 0, 600),
        queue_minutes=_int("QUEUE_MINUTES", 30),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
