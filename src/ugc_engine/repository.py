"""All SQL lives here. Functions take/return plain dicts."""
from __future__ import annotations

from . import clock
from .db import connect

INSERT_COLUMNS = (
    "dedupe_key", "brand_name", "platform", "source_url", "brand_domain", "niche", "contact_email",
    "decision_maker", "first_name", "intent_score", "competition_level", "raw_snippet", "hook_concepts",
    "email_subject", "step1_body", "step2_body", "step3_body", "is_demo",
)
DEFAULTS = {"intent_score": 50, "is_demo": 0, "competition_level": "Low"}
CLOSED_STATUSES = ("Closed Won", "Archived", "Negotiating")
STEP_STATUS = {1: "Step 1 Sent", 2: "Step 2 Sent", 3: "Sequence Complete"}


# ---------------- leads ----------------
def lead_exists(key: str) -> bool:
    with connect() as c:
        return c.execute("SELECT 1 FROM leads WHERE dedupe_key=?", (key,)).fetchone() is not None


def save_lead(data: dict) -> bool:
    values = [data.get(col, DEFAULTS.get(col, "")) for col in INSERT_COLUMNS]
    with connect() as c:
        cur = c.execute(
            f"INSERT OR IGNORE INTO leads ({','.join(INSERT_COLUMNS)}, created_at) "
            f"VALUES ({','.join('?' * len(INSERT_COLUMNS))}, ?)",
            [*values, clock.ts()],
        )
        return cur.rowcount > 0


def get_lead(lead_id: int) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row) if row else None


def list_leads() -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM leads ORDER BY is_demo, intent_score DESC, id DESC")]


def update_content(lead_id: int, email: str, subject: str, s1: str, s2: str, s3: str) -> None:
    with connect() as c:
        c.execute(
            "UPDATE leads SET contact_email=?, email_subject=?, step1_body=?, step2_body=?, step3_body=? WHERE id=?",
            (email.strip().lower(), subject.strip(), s1, s2, s3, lead_id),
        )


def close_lead(lead_id: int, kind: str, email: str = "") -> None:
    """kind: replied | unsubscribed | bounced. Stops the sequence for good."""
    status, column = {
        "replied": ("Replied", "replied"),
        "unsubscribed": ("Unsubscribed", "unsubscribed"),
        "bounced": ("Bounced", "bounced"),
    }[kind]
    with connect() as c:
        c.execute(f"UPDATE leads SET {column}=1, status=?, next_followup_at='' WHERE id=?", (status, lead_id))
    if kind in ("unsubscribed", "bounced") and email:
        suppress(email, kind)


def set_status(lead_id: int, status: str) -> None:
    if status == "Replied":
        return close_lead(lead_id, "replied")
    if status == "Unsubscribed":
        lead = get_lead(lead_id)
        return close_lead(lead_id, "unsubscribed", (lead or {}).get("contact_email", ""))
    with connect() as c:
        if status in CLOSED_STATUSES:
            c.execute("UPDATE leads SET status=?, next_followup_at='' WHERE id=?", (status, lead_id))
        else:
            c.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))


# ---------------- sending state ----------------
def claim_step(lead_id: int, expected_step: int, new_status: str) -> bool:
    """Atomically move a lead to the next step so two processes can never send the same step twice."""
    with connect() as c:
        cur = c.execute(
            """UPDATE leads SET sequence_step=?, status=?, next_followup_at=''
               WHERE id=? AND sequence_step=? AND replied=0 AND bounced=0 AND unsubscribed=0""",
            (expected_step + 1, new_status, lead_id, expected_step),
        )
        return cur.rowcount == 1


def release_claim(lead: dict) -> None:
    """Undo claim_step after a failed send."""
    with connect() as c:
        c.execute(
            "UPDATE leads SET sequence_step=?, status=?, next_followup_at=? WHERE id=?",
            (lead["sequence_step"], lead["status"], lead["next_followup_at"], lead["id"]),
        )


def finalize_send(lead_id: int, step: int, recipient: str, anchor: str, next_followup: str, live: bool) -> None:
    now = clock.now()
    with connect() as c:
        c.execute(
            """UPDATE leads SET last_sent_at=?, next_followup_at=?, message_id_header=?,
               first_sent_at=CASE WHEN first_sent_at='' THEN ? ELSE first_sent_at END WHERE id=?""",
            (clock.ts(now), next_followup, anchor, clock.ts(now), lead_id),
        )
        c.execute(
            "INSERT INTO send_logs (lead_id, step, recipient, sent_date, sent_at, live) VALUES (?,?,?,?,?,?)",
            (lead_id, step, recipient, now.strftime("%Y-%m-%d"), clock.ts(now), 1 if live else 0),
        )


def sends_today() -> int:
    with connect() as c:
        return c.execute(
            "SELECT COUNT(*) FROM send_logs WHERE sent_date=?", (clock.now().strftime("%Y-%m-%d"),)
        ).fetchone()[0]


def contacted_elsewhere(email: str, lead_id: int) -> bool:
    with connect() as c:
        return c.execute(
            "SELECT 1 FROM send_logs WHERE lower(recipient)=? AND lead_id!=? AND live=1", (email.lower(), lead_id)
        ).fetchone() is not None


def due_followups(now_str: str) -> list[int]:
    with connect() as c:
        return [r["id"] for r in c.execute(
            """SELECT id FROM leads WHERE sequence_step IN (1,2) AND replied=0 AND bounced=0 AND unsubscribed=0
               AND status NOT IN ('Closed Won','Archived','Negotiating')
               AND next_followup_at!='' AND next_followup_at<=? ORDER BY next_followup_at""",
            (now_str,),
        )]


def auto_first_candidates(min_score: int) -> list[int]:
    with connect() as c:
        return [r["id"] for r in c.execute(
            """SELECT id FROM leads WHERE sequence_step=0 AND status='New' AND is_demo=0 AND intent_score>=?
               AND contact_email LIKE '%@%' ORDER BY intent_score DESC""",
            (min_score,),
        )]


def inbox_candidates() -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT id, contact_email, first_sent_at FROM leads
               WHERE sequence_step>0 AND replied=0 AND bounced=0 AND unsubscribed=0 AND first_sent_at!=''"""
        )]


# ---------------- suppression ----------------
def is_suppressed(email: str) -> bool:
    with connect() as c:
        return c.execute("SELECT 1 FROM suppression WHERE email=?", (email.lower(),)).fetchone() is not None


def suppress(email: str, reason: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO suppression (email, reason, added_at) VALUES (?,?,?)",
            (email.lower(), reason, clock.ts()),
        )


# ---------------- job requests (web -> worker) and key/value ----------------
def enqueue_job(kind: str) -> bool:
    with connect() as c:
        if c.execute("SELECT 1 FROM job_requests WHERE kind=? AND done_at=''", (kind,)).fetchone():
            return False
        c.execute("INSERT INTO job_requests (kind, requested_at) VALUES (?,?)", (kind, clock.ts()))
        return True


def pop_jobs() -> set[str]:
    with connect() as c:
        kinds = {r["kind"] for r in c.execute("SELECT kind FROM job_requests WHERE done_at=''")}
        c.execute("UPDATE job_requests SET done_at=? WHERE done_at=''", (clock.ts(),))
    return kinds


def set_kv(key: str, value: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO kv (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_kv(key: str, default: str = "") -> str:
    with connect() as c:
        row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default
