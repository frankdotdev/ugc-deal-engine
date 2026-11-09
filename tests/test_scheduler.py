from ugc_engine import repository as repo
from ugc_engine import scheduler


def test_dashboard_requested_jobs_are_run_once(settings, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "run_discovery", lambda s: calls.append("scan"))
    monkeypatch.setattr(scheduler, "process_queue", lambda s: calls.append("queue"))
    repo.enqueue_job("scan")
    repo.enqueue_job("queue")
    scheduler.process_job_requests()
    scheduler.process_job_requests()
    assert sorted(calls) == ["queue", "scan"]


def test_scheduler_registers_jobs(settings):
    sched = scheduler.build_scheduler(settings)
    ids = {job.id for job, *_ in sched._pending_jobs}
    assert ids == {"discovery", "queue", "job_requests"}
