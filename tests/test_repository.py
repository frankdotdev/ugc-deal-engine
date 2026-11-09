from tests.conftest import new_lead
from ugc_engine import repository as repo


def test_save_dedupes(settings):
    assert repo.save_lead(new_lead()) is True
    assert repo.save_lead(new_lead()) is False
    assert repo.lead_exists("k1")


def test_close_lead_suppresses_optouts_and_bounces(settings):
    repo.save_lead(new_lead())
    repo.close_lead(1, "unsubscribed", "Owner@Acme.test")
    assert repo.is_suppressed("owner@acme.test")
    assert repo.get_lead(1)["status"] == "Unsubscribed"


def test_claim_step_is_atomic(settings):
    repo.save_lead(new_lead())
    assert repo.claim_step(1, 0, "Step 1 Sent") is True
    assert repo.claim_step(1, 0, "Step 1 Sent") is False  # second claimer loses


def test_jobs_queue_dedupes_and_pops(settings):
    assert repo.enqueue_job("scan") is True
    assert repo.enqueue_job("scan") is False
    assert repo.pop_jobs() == {"scan"}
    assert repo.pop_jobs() == set()


def test_kv(settings):
    repo.set_kv("a", "1")
    repo.set_kv("a", "2")
    assert repo.get_kv("a") == "2" and repo.get_kv("missing", "d") == "d"
