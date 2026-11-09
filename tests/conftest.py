import pytest

from ugc_engine import config, db

ENV_DEFAULTS = {
    "APP_ENV": "development", "DRY_RUN": "true", "SEND_JITTER_SECONDS": "0-0", "DASHBOARD_PASSWORD": "test-password-123",
    "SERPER_API_KEY": "", "APIFY_API_TOKEN": "", "GEMINI_API_KEY": "", "HUNTER_API_KEY": "",
    "SMTP_EMAIL": "", "SMTP_APP_PASSWORD": "", "SENDER_POSTAL_ADDRESS": "", "AUTO_SEND_FIRST": "false",
    "SEND_WINDOW_UTC": "00-24", "DAILY_SEND_LIMIT": "20",
}


@pytest.fixture
def make_settings(tmp_path, monkeypatch):
    def _make(**overrides):
        env = {**ENV_DEFAULTS, "DB_PATH": str(tmp_path / "test.db"), **overrides}
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        config.get_settings.cache_clear()
        settings = config.get_settings()
        db.init_db()
        return settings
    yield _make
    config.get_settings.cache_clear()


@pytest.fixture
def settings(make_settings):
    return make_settings()


def new_lead(**kw):
    base = {
        "dedupe_key": "k1", "brand_name": "Acme", "platform": "X (Twitter)", "source_url": "https://x.com/a/1",
        "niche": "skincare", "contact_email": "owner@acme.test", "intent_score": 80, "raw_snippet": "need UGC creators",
        "email_subject": "ideas for acme", "step1_body": "one", "step2_body": "two", "step3_body": "three",
    }
    base.update(kw)
    return base
