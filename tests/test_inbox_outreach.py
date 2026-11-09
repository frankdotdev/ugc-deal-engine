from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from tests.conftest import new_lead
from ugc_engine import clock, inbox, outreach
from ugc_engine import repository as repo


def _msg(subject="Re: hi", body="sounds great", **headers):
    m = EmailMessage()
    m["Subject"] = subject
    for k, v in headers.items():
        m[k.replace("_", "-")] = v
    m.set_content(body)
    return m


def test_imap_date_is_locale_independent():
    assert inbox.imap_date("2026-11-09 10:00:00") == "09-Nov-2026"


def test_classify_reply():
    assert inbox.classify_reply(_msg()) == "reply"
    assert inbox.classify_reply(_msg(body="Please unsubscribe me")) == "optout"
    assert inbox.classify_reply(_msg(subject="Automatic reply: away")) == "auto"
    assert inbox.classify_reply(_msg(Auto_Submitted="auto-replied")) == "auto"


def test_send_window(settings, make_settings):
    s = make_settings(SEND_WINDOW_UTC="08-18")
    monday_noon = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    assert outreach.in_send_window(s, monday_noon)
    assert not outreach.in_send_window(s, monday_noon.replace(hour=20))
    assert not outreach.in_send_window(s, datetime(2026, 11, 14, 12, tzinfo=timezone.utc))  # Saturday


def test_queue_sends_only_due_followups(settings):
    repo.save_lead(new_lead())
    repo.save_lead(new_lead(dedupe_key="k2", contact_email="b@b.test"))
    from ugc_engine import mailer
    mailer.send_step(1, settings)
    mailer.send_step(2, settings)
    # lead 1: follow-up due now; lead 2: due next week
    from ugc_engine.db import connect
    with connect() as c:
        c.execute("UPDATE leads SET next_followup_at=? WHERE id=1", (clock.ts(clock.now() - timedelta(hours=1)),))
    stats = outreach.process_queue(settings)
    assert stats["followups"] == 1
    assert repo.get_lead(1)["sequence_step"] == 2 and repo.get_lead(2)["sequence_step"] == 1


def test_queue_skips_closed_leads(settings):
    repo.save_lead(new_lead())
    from ugc_engine import mailer
    from ugc_engine.db import connect
    mailer.send_step(1, settings)
    repo.close_lead(1, "replied")
    with connect() as c:
        c.execute("UPDATE leads SET next_followup_at=? WHERE id=1", (clock.ts(clock.now() - timedelta(hours=1)),))
    assert outreach.process_queue(settings)["followups"] == 0
