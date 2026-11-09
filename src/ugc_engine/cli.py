"""Command line entry point:  ugc-engine <command>"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

from . import __version__
from .config import ConfigError, get_settings
from .db import init_db
from .logging_setup import configure


def _cmd_check(_args) -> int:
    s = get_settings()
    print(f"Environment: {s.env}   DB: {s.db_path}")
    status = 0
    for role in ("web", "worker"):
        for p in s.problems(role):
            print(f"[ERROR:{role}] {p}")
            status = 1
    for w in s.warnings():
        print(f"[warn] {w}")
    print("Config OK" if status == 0 else "Config has blocking problems")
    return status


def _cmd_web(_args) -> int:
    from .web import create_app
    s = get_settings()
    app = create_app(s)
    if s.password_generated:
        print(f"Dashboard login -> user: admin  password: {s.dashboard_password}")
    app.run(host=s.host, port=s.port, debug=False, threaded=True)
    return 0


def _cmd_worker(_args) -> int:
    from .scheduler import run_worker
    run_worker()
    return 0


def _cmd_scan(_args) -> int:
    from .discovery import run_discovery
    init_db()
    print(run_discovery())
    return 0


def _cmd_queue(_args) -> int:
    from .outreach import process_queue
    init_db()
    print(process_queue())
    return 0


def _cmd_seed(_args) -> int:
    from .discovery import seed_demo
    init_db()
    print(f"Added {seed_demo()} demo leads (flagged, never sent in live mode).")
    return 0


def _cmd_backup(args) -> int:
    s = get_settings()
    init_db()
    os.makedirs(os.path.dirname(os.path.abspath(args.path)), exist_ok=True)
    src, dst = sqlite3.connect(s.db_path), sqlite3.connect(args.path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    print(f"Backup written to {args.path}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ugc-engine", description="UGC Deal Engine")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, helptext in (
        ("check-config", _cmd_check, "validate configuration"),
        ("web", _cmd_web, "run the dashboard (dev server; use gunicorn in production)"),
        ("worker", _cmd_worker, "run the scheduler worker (discovery, inbox, follow-ups)"),
        ("scan", _cmd_scan, "run one discovery scan now"),
        ("queue", _cmd_queue, "run one inbox check + follow-up pass now"),
        ("seed-demo", _cmd_seed, "insert flagged demo leads"),
    ):
        sub.add_parser(name, help=helptext).set_defaults(func=fn)
    backup = sub.add_parser("backup", help="write a consistent copy of the database")
    backup.add_argument("path")
    backup.set_defaults(func=_cmd_backup)

    args = parser.parse_args(argv)
    try:
        s = get_settings()
        configure(s.log_level)
        return args.func(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
