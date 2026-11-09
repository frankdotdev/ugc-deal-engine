from __future__ import annotations

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from ..config import ConfigError, Settings, get_settings
from ..db import init_db
from .security import init_security
from .views import bp


def create_app(settings: Settings | None = None) -> Flask:
    s = settings or get_settings()
    problems = s.problems("web")
    if problems:
        raise ConfigError("; ".join(problems))
    init_db()
    app = Flask(__name__)
    app.config.update(
        SETTINGS=s,
        SECRET_KEY=s.secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=s.cookie_secure,
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if s.trust_proxy:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    init_security(app, s)
    app.register_blueprint(bp)
    return app
