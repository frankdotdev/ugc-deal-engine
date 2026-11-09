"""Scheduled outreach run: inbox first, then due follow-ups, then (optionally) approved first touches."""
from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime

from . import clock
from . import repository as repo
from .config import Settings, get_settings
from .inbox import process_inbox
from .mailer import send_step

log = logging.getLogger(__name__)
_lock = threading.Lock()


def in_send_window(s: Settings, at: datetime | None = None) -> bool:
    at = at or clock.now()
    start, end = s.send_window_utc
    return at.weekday() < 5 and start <= at.hour < end


def process_queue(s: Settings | None = None) -> dict:
    s = s or get_settings()
    if not _lock.acquire(blocking=False):
        return {"busy": True}
    try:
        stats = process_inbox(s)  # always first: nobody who replied gets another email
        stats.update(followups=0, first_touches=0)
        if not in_send_window(s):
            stats["note"] = "Outside send window: inbox checked, nothing sent."
            return stats
        batches = [("followups", repo.due_followups(clock.ts()))]
        if s.auto_send_first:
            batches.append(("first_touches", repo.auto_first_candidates(s.auto_send_min_score)))
        for key, ids in batches:
            for lead_id in ids:
                ok, message = send_step(lead_id, s)
                if ok:
                    stats[key] += 1
                    if s.live_email and s.send_jitter[1] > 0:
                        time.sleep(random.uniform(*s.send_jitter))
                elif message.startswith("Daily limit"):
                    return stats
        return stats
    finally:
        _lock.release()
