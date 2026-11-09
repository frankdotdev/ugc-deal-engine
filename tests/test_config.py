import pytest

from ugc_engine.config import ConfigError


def test_defaults_are_safe(settings):
    assert settings.dry_run is True and not settings.live_email
    assert settings.followup_delays == (3, 7)


def test_production_requires_strong_password(make_settings):
    s = make_settings(APP_ENV="production", DASHBOARD_PASSWORD="short")
    assert any("DASHBOARD_PASSWORD" in p for p in s.problems("web"))


def test_live_mode_requires_identity_and_address(make_settings):
    s = make_settings(DRY_RUN="false", SMTP_EMAIL="me@x.test", SMTP_APP_PASSWORD="abcd")
    problems = " ".join(s.problems("worker"))
    assert "SENDER_POSTAL_ADDRESS" in problems and "SMTP_SENDER_NAME" in problems and "PORTFOLIO_URL" in problems


def test_live_mode_ok_when_complete(make_settings):
    s = make_settings(DRY_RUN="false", SMTP_EMAIL="me@x.test", SMTP_APP_PASSWORD="abcd", SENDER_POSTAL_ADDRESS="1 Road",
                      SMTP_SENDER_NAME="Ada", PORTFOLIO_URL="https://ada.test")
    assert s.problems("worker") == [] and s.live_email


def test_bad_values_raise(make_settings):
    with pytest.raises(ConfigError):
        make_settings(SEND_WINDOW_UTC="18-08")
