"""IMAP: detect replies, opt-outs and bounces so sequences stop on their own."""
from __future__ import annotations

import imaplib
import logging
from datetime import datetime
from email import message_from_bytes
from email.message import Message

from . import repository as repo
from .config import Settings, get_settings
from .enrichment import EMAIL_RE

log = logging.getLogger(__name__)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
OPT_OUT = (
    "unsubscribe", "remove me", "stop email", "stop contact", "do not contact", "no thanks", "no thank you",
    "not interested", "take me off",
)


def imap_date(value: str) -> str:
    """'2026-11-09 10:00:00' -> '09-Nov-2026' (locale independent, as IMAP requires)."""
    d = datetime.strptime(value[:10], "%Y-%m-%d")
    return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


def body_text(m: Message) -> str:
    if m.is_multipart():
        parts = [p.get_payload(decode=True) or b"" for p in m.walk() if p.get_content_type() == "text/plain"]
    else:
        parts = [m.get_payload(decode=True) or b""]
    return b"\n".join(parts).decode("utf-8", "ignore")


def classify_reply(m: Message) -> str:
    """'auto' (out-of-office etc, ignore), 'optout', or 'reply'."""
    subject = (m.get("Subject") or "").lower()
    if m.get("Auto-Submitted", "no").lower() != "no" or "automatic reply" in subject or "out of office" in subject:
        return "auto"
    if any(k in body_text(m).lower()[:500] for k in OPT_OUT):
        return "optout"
    return "reply"


def _search(mail: imaplib.IMAP4_SSL, criteria: str) -> list[bytes]:
    typ, data = mail.search(None, criteria)
    return data[0].split() if typ == "OK" and data and data[0] else []


def process_inbox(s: Settings | None = None) -> dict:
    s = s or get_settings()
    stats = {"replies": 0, "optouts": 0, "bounces": 0}
    if not s.live_email:
        return stats
    leads = repo.inbox_candidates()
    if not leads:
        return stats
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(s.imap_host, s.imap_port)
        mail.login(s.smtp_email, s.smtp_app_password)
        mail.select("INBOX")
        since_all = imap_date(min(lead["first_sent_at"] for lead in leads))
        bounce_blobs: list[str] = []
        for sender in ("mailer-daemon", "postmaster"):
            for mid in _search(mail, f'(FROM "{sender}" SINCE {since_all})')[-100:]:
                typ, d = mail.fetch(mid, "(BODY.PEEK[])")
                if typ == "OK" and d and d[0]:
                    bounce_blobs.append(d[0][1].decode("utf-8", "ignore").lower())
        for lead in leads:
            addr = lead["contact_email"].strip().lower()
            if not EMAIL_RE.fullmatch(addr):
                continue
            if any(addr in blob for blob in bounce_blobs):
                repo.close_lead(lead["id"], "bounced", addr)
                stats["bounces"] += 1
                continue
            ids = _search(mail, f'(FROM "{addr}" SINCE {imap_date(lead["first_sent_at"])})')
            if not ids:
                continue
            typ, d = mail.fetch(ids[-1], "(BODY.PEEK[])")
            if typ != "OK" or not d or not d[0]:
                continue
            kind = classify_reply(message_from_bytes(d[0][1]))
            if kind == "optout":
                repo.close_lead(lead["id"], "unsubscribed", addr)
                stats["optouts"] += 1
            elif kind == "reply":
                repo.close_lead(lead["id"], "replied")
                stats["replies"] += 1
    except Exception as exc:
        log.warning("IMAP check failed: %s", exc)
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass
    return stats
