"""Basic-auth login (with brute-force throttle), CSRF protection and security headers."""
from __future__ import annotations

import hmac
import secrets
import time

from flask import Flask, Response, abort, request, session

from ..config import Settings

WINDOW_SECONDS = 600
MAX_FAILURES = 10
_failures: dict[str, list[float]] = {}


def _safe_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def init_security(app: Flask, s: Settings) -> None:
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def _authenticate():
        if request.endpoint in ("views.healthz", "static"):
            return None
        ip = request.remote_addr or "unknown"
        now = time.time()
        recent = [t for t in _failures.get(ip, []) if now - t < WINDOW_SECONDS]
        if len(recent) >= MAX_FAILURES:
            return Response("Too many failed logins. Try again later.", 429)
        auth = request.authorization
        if auth and _safe_equal(auth.password or "", s.dashboard_password):
            return None
        if auth:
            recent.append(now)
        _failures[ip] = recent
        return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="UGC Engine"'})

    @app.before_request
    def _check_csrf():
        if request.method == "POST":
            expected = session.get("csrf", "")
            if not expected or not _safe_equal(expected, request.form.get("csrf_token", "")):
                abort(400, "Invalid or missing CSRF token. Reload the page and try again.")

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; form-action 'self'"
        resp.headers["Cache-Control"] = "no-store"
        return resp
