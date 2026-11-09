"""Builds and sends sequence emails (threaded, with opt-out footer) and enforces send safety rules."""
from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from . import ai, clock
from . import repository as repo
from .config import Settings, get_settings
from .enrichment import EMAIL_RE
from .repository import STEP_STATUS

log = logging.getLogger(__name__)


def signature(s: Settings) -> str:
    lines = ["--", s.sender_name, s.portfolio_url]
    if s.postal_address:
        lines.append(s.postal_address)
    lines.append('Not relevant? Reply "no thanks" and I won\'t contact you again.')
    return "\n".join(lines)


def blocker(lead: dict, s: Settings) -> str | None:
    """Reason this lead must not be emailed right now, or None if it is clear to send."""
    addr = (lead["contact_email"] or "").strip().lower()
    if lead["replied"] or lead["bounced"] or lead["unsubscribed"]:
        return "Lead is closed (replied / bounced / unsubscribed)."
    if lead["status"] in ("Archived", "Closed Won"):
        return f"Lead is {lead['status']}."
    if not EMAIL_RE.fullmatch(addr):
        return "Add a valid recipient email first."
    if repo.is_suppressed(addr):
        return "Address is on the suppression list."
    if lead["sequence_step"] >= 3:
        return "All 3 steps already sent."
    if repo.sends_today() >= s.daily_send_limit:
        return f"Daily limit of {s.daily_send_limit} reached; try tomorrow."
    if s.live_email:
        if lead["is_demo"]:
            return "Demo lead: never sent in live mode."
        if not s.postal_address:
            return "Set SENDER_POSTAL_ADDRESS (required in commercial email, e.g. CAN-SPAM)."
        if lead["sequence_step"] == 0 and repo.contacted_elsewhere(addr, lead["id"]):
            return "This address was already contacted via another lead."
    return None


def build_message(lead: dict, step: int, s: Settings) -> tuple[EmailMessage, str, str]:
    base = (lead["email_subject"] or f"native video ideas for {lead['brand_name']}").strip()
    body = lead[f"step{step}_body"] or ai.fallback_sequence(
        lead["brand_name"], lead["platform"], lead["niche"], s)[f"step{step}_body"]
    subject = base if step == 1 else (base if base.lower().startswith("re:") else f"Re: {base}")

    msg = EmailMessage()
    msg["From"] = formataddr((s.sender_name, s.smtp_email or "demo@localhost"))
    msg["To"] = lead["contact_email"].strip()
    msg["Subject"] = subject
    domain = s.smtp_email.split("@")[-1] if "@" in s.smtp_email else "ugcengine.local"
    msgid = make_msgid(domain=domain)
    msg["Message-ID"] = msgid
    anchor = lead["message_id_header"] or msgid
    if step > 1:
        msg["In-Reply-To"] = anchor
        msg["References"] = anchor
    if s.smtp_email:
        msg["List-Unsubscribe"] = f"<mailto:{s.smtp_email}?subject=unsubscribe>"
    greeting = f"Hi {lead['first_name']}," if lead["first_name"] else "Hi there,"
    msg.set_content(f"{greeting}\n\n{body.strip()}\n\n{signature(s)}")
    return msg, subject, anchor


def _smtp_send(msg: EmailMessage, s: Settings) -> None:
    with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ssl.create_default_context(), timeout=25) as server:
        server.login(s.smtp_email, s.smtp_app_password)
        server.send_message(msg)


def send_step(lead_id: int, s: Settings | None = None) -> tuple[bool, str]:
    """Send the next sequence step for a lead. Returns (ok, human-readable message)."""
    s = s or get_settings()
    lead = repo.get_lead(lead_id)
    if not lead:
        return False, "Lead not found."
    reason = blocker(lead, s)
    if reason:
        return False, reason

    step = lead["sequence_step"] + 1
    msg, subject, anchor = build_message(lead, step, s)
    recipient = lead["contact_email"].strip()
    if not repo.claim_step(lead_id, lead["sequence_step"], STEP_STATUS[step]):
        return False, "Another process just updated this lead; refresh and retry."

    live = s.live_email
    try:
        if live:
            _smtp_send(msg, s)
        else:
            log.info("[SIMULATED] step %s -> %s | %s", step, recipient, subject)
    except Exception as exc:
        repo.release_claim(lead)
        log.error("SMTP error sending to %s: %s", recipient, exc)
        return False, f"SMTP error: {exc}"

    delay = s.followup_delays[step - 1] if step <= len(s.followup_delays) else 0
    next_followup = clock.ts(clock.now() + timedelta(days=delay)) if delay else ""
    repo.finalize_send(lead_id, step, recipient, anchor, next_followup, live)
    return True, f"Step {step}/3 {'sent' if live else 'simulated (DRY_RUN or no SMTP credentials)'} to {recipient}."
