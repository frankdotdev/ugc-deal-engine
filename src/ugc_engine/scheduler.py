"""Background worker: periodic discovery, inbox/follow-up processing, and dashboard-requested jobs."""
from __future__ import annotations

import logging
import signal
from datetime import timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from . import clock
from . import repository as repo
from .config import ConfigError, Settings, get_settings
from .db import init_db
from .discovery import run_discovery
from .outreach import process_queue

log = logging.getLogger(__name__)


def process_job_requests() -> None:
    """Run work the dashboard asked for (the web process never does slow work itself)."""
    kinds = repo.pop_jobs()
    s = get_settings()
    if "scan" in kinds:
        run_discovery(s)
    if "queue" in kinds:
        process_queue(s)


def build_scheduler(s: Settings) -> BlockingScheduler:
    sched = BlockingScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300})
    sched.add_job(run_discovery, "interval", hours=s.discovery_hours, args=[s], id="discovery",
                  next_run_time=clock.now() + timedelta(seconds=30))
    sched.add_job(process_queue, "interval", minutes=s.queue_minutes, args=[s], id="queue")
    sched.add_job(process_job_requests, "interval", seconds=15, id="job_requests")
    return sched


def run_worker() -> None:
    s = get_settings()
    problems = s.problems("worker")
    if problems:
        raise ConfigError("; ".join(problems))
    init_db()
    for w in s.warnings():
        log.warning(w)
    sched = build_scheduler(s)

    def _stop(signum, _frame):
        log.info("Signal %s received, shutting down worker", signum)
        sched.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _stop)
    log.info("Worker started (%s sending)", "LIVE" if s.live_email else "SIMULATED")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass
