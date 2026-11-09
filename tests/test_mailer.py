from tests.conftest import new_lead
from ugc_engine import mailer
from ugc_engine import repository as repo


def test_sequence_progresses_and_threads(settings):
    repo.save_lead(new_lead())
    ok, _ = mailer.send_step(1, settings)
    assert ok
    lead = repo.get_lead(1)
    assert lead["sequence_step"] == 1 and lead["next_followup_at"] and lead["message_id_header"]
    msg, subject, _ = mailer.build_message(lead, 2, settings)
    assert subject == "Re: ideas for acme"
    assert msg["In-Reply-To"] == lead["message_id_header"]
    assert 'Reply "no thanks"' in msg.get_content()


def test_stops_after_three_steps(settings):
    repo.save_lead(new_lead())
    results = [mailer.send_step(1, settings)[0] for _ in range(4)]
    assert results == [True, True, True, False]


def test_blocks_invalid_email_closed_and_suppressed(settings):
    repo.save_lead(new_lead(contact_email="not-an-email"))
    assert "valid recipient" in mailer.send_step(1, settings)[1]
    repo.save_lead(new_lead(dedupe_key="k2", contact_email="a@b.test"))
    repo.suppress("a@b.test", "bounced")
    assert "suppression" in mailer.send_step(2, settings)[1]
    repo.save_lead(new_lead(dedupe_key="k3", contact_email="c@d.test"))
    repo.close_lead(3, "replied")
    assert "closed" in mailer.send_step(3, settings)[1]


def test_daily_limit(make_settings):
    s = make_settings(DAILY_SEND_LIMIT="1")
    repo.save_lead(new_lead())
    repo.save_lead(new_lead(dedupe_key="k2", contact_email="x@y.test"))
    assert mailer.send_step(1, s)[0] is True
    assert "Daily limit" in mailer.send_step(2, s)[1]


def test_live_mode_never_sends_demo_leads(make_settings, monkeypatch):
    s = make_settings(DRY_RUN="false", SMTP_EMAIL="me@x.test", SMTP_APP_PASSWORD="abcd", SENDER_POSTAL_ADDRESS="1 Road",
                      SMTP_SENDER_NAME="Ada", PORTFOLIO_URL="https://ada.test")
    sent = []
    monkeypatch.setattr(mailer, "_smtp_send", lambda msg, st: sent.append(msg))
    repo.save_lead(new_lead(is_demo=1))
    assert "Demo lead" in mailer.send_step(1, s)[1] and not sent


def test_live_send_failure_rolls_back_claim(make_settings, monkeypatch):
    s = make_settings(DRY_RUN="false", SMTP_EMAIL="me@x.test", SMTP_APP_PASSWORD="abcd", SENDER_POSTAL_ADDRESS="1 Road",
                      SMTP_SENDER_NAME="Ada", PORTFOLIO_URL="https://ada.test")
    def boom(msg, st):
        raise OSError("smtp down")
    monkeypatch.setattr(mailer, "_smtp_send", boom)
    repo.save_lead(new_lead())
    ok, message = mailer.send_step(1, s)
    assert not ok and "SMTP error" in message
    assert repo.get_lead(1)["sequence_step"] == 0 and repo.sends_today() == 0


def test_live_send_blocks_duplicate_recipient_across_leads(make_settings, monkeypatch):
    s = make_settings(DRY_RUN="false", SMTP_EMAIL="me@x.test", SMTP_APP_PASSWORD="abcd", SENDER_POSTAL_ADDRESS="1 Road",
                      SMTP_SENDER_NAME="Ada", PORTFOLIO_URL="https://ada.test")
    monkeypatch.setattr(mailer, "_smtp_send", lambda msg, st: None)
    repo.save_lead(new_lead())
    repo.save_lead(new_lead(dedupe_key="k2"))
    assert mailer.send_step(1, s)[0] is True
    assert "already contacted" in mailer.send_step(2, s)[1]
