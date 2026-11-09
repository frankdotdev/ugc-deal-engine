from __future__ import annotations

import csv
import io

from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request, url_for

from .. import mailer
from .. import repository as repo
from ..db import connect

bp = Blueprint("views", __name__)

STATUSES = ["New", "Step 1 Sent", "Step 2 Sent", "Sequence Complete", "Replied", "Negotiating", "Closed Won", "Archived", "Unsubscribed"]
TABS = [("all", "All"), ("ready", "Ready to pitch"), ("active", "In sequence"), ("replied", "Replied / won"), ("closed", "Closed")]


def _closed(r: dict) -> bool:
    return bool(r["replied"] or r["bounced"] or r["unsubscribed"])


VIEWS = {
    "all": lambda r: True,
    "ready": lambda r: r["sequence_step"] == 0 and r["status"] == "New",
    "active": lambda r: r["sequence_step"] in (1, 2) and not _closed(r),
    "replied": lambda r: r["status"] in ("Replied", "Negotiating", "Closed Won"),
    "closed": lambda r: r["status"] in ("Archived", "Unsubscribed", "Bounced", "Sequence Complete"),
}


def _back(message: str):
    return redirect(url_for("views.index", msg=message, f=request.args.get("f", "all")))


@bp.get("/healthz")
def healthz():
    with connect() as c:
        c.execute("SELECT 1").fetchone()
    return jsonify(status="ok")


@bp.get("/")
def index():
    s = current_app.config["SETTINGS"]
    current = request.args.get("f", "all")
    rows = repo.list_leads()
    visible = [r for r in rows if VIEWS.get(current, VIEWS["all"])(r)]
    return render_template(
        "index.html", leads=visible, f=current, tabs=TABS, statuses=STATUSES, msg=request.args.get("msg", ""),
        last_scan=repo.get_kv("last_scan", "No scan has run yet."),
        total=len(rows), ready=sum(1 for r in rows if VIEWS["ready"](r) and not r["is_demo"]),
        active=sum(1 for r in rows if VIEWS["active"](r)), replies=sum(1 for r in rows if r["replied"]),
        today=repo.sends_today(), limit=s.daily_send_limit,
        mode="LIVE sending" if s.live_email else "SIMULATION: no emails leave",
    )


@bp.post("/scan")
def scan():
    queued = repo.enqueue_job("scan")
    return _back("Scan requested; the worker picks it up within ~15 seconds." if queued else "A scan is already queued.")


@bp.post("/queue")
def queue():
    queued = repo.enqueue_job("queue")
    return _back("Inbox check requested; the worker runs it shortly." if queued else "A run is already queued.")


def _apply_edits(lead_id: int) -> None:
    f = request.form
    repo.update_content(
        lead_id, f.get("contact_email", ""), f.get("email_subject", ""),
        f.get("step1_body", ""), f.get("step2_body", ""), f.get("step3_body", ""),
    )


@bp.post("/save/<int:lead_id>")
def save(lead_id: int):
    _apply_edits(lead_id)
    return _back(f"Saved edits for lead #{lead_id}.")


@bp.post("/send/<int:lead_id>")
def send(lead_id: int):
    _apply_edits(lead_id)
    ok, message = mailer.send_step(lead_id, current_app.config["SETTINGS"])
    return _back(("OK: " if ok else "Not sent: ") + message)


@bp.post("/status/<int:lead_id>")
def status(lead_id: int):
    new_status = request.form.get("status", "New")
    if new_status not in STATUSES:
        return _back("Unknown status.")
    repo.set_status(lead_id, new_status)
    return _back(f"Lead #{lead_id} set to {new_status}.")


def _safe_cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text  # block CSV formula injection


@bp.get("/export.csv")
def export_csv():
    fields = ["id", "brand_name", "platform", "brand_domain", "contact_email", "decision_maker", "intent_score",
              "status", "sequence_step", "last_sent_at", "source_url"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(fields)
    for row in repo.list_leads():
        writer.writerow([_safe_cell(row[k]) for k in fields])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=ugc_leads.csv"})
