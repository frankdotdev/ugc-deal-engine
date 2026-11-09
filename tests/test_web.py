import base64

import pytest

from tests.conftest import new_lead
from ugc_engine import repository as repo
from ugc_engine.web import create_app

AUTH = {"Authorization": "Basic " + base64.b64encode(b"admin:test-password-123").decode()}


@pytest.fixture
def client(settings):
    repo.save_lead(new_lead())
    return create_app(settings).test_client()


def _token(client):
    client.get("/", headers=AUTH)
    with client.session_transaction() as sess:
        return sess["csrf"]


def test_requires_login(client):
    assert client.get("/").status_code == 401
    bad = {"Authorization": "Basic " + base64.b64encode(b"admin:wrong").decode()}
    assert client.get("/", headers=bad).status_code == 401


def test_healthz_is_public(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_dashboard_renders_and_sets_security_headers(client):
    r = client.get("/", headers=AUTH)
    assert r.status_code == 200 and b"Acme" in r.data
    assert r.headers["X-Frame-Options"] == "DENY" and "Content-Security-Policy" in r.headers


def test_post_requires_csrf(client):
    assert client.post("/scan", headers=AUTH).status_code == 400
    r = client.post("/scan", headers=AUTH, data={"csrf_token": _token(client)})
    assert r.status_code == 302 and repo.pop_jobs() == {"scan"}


def test_send_and_status_flow(client):
    tok = _token(client)
    client.post("/send/1", headers=AUTH, data={"csrf_token": tok, "contact_email": "new@acme.test", "email_subject": "s",
                                                "step1_body": "a", "step2_body": "b", "step3_body": "c"})
    lead = repo.get_lead(1)
    assert lead["contact_email"] == "new@acme.test" and lead["sequence_step"] == 1
    client.post("/status/1", headers=AUTH, data={"csrf_token": tok, "status": "Replied"})
    assert repo.get_lead(1)["replied"] == 1


def test_csv_export_blocks_formula_injection(client):
    repo.save_lead(new_lead(dedupe_key="k9", brand_name="=HYPERLINK(\"http://evil\")"))
    body = client.get("/export.csv", headers=AUTH).get_data(as_text=True)
    assert "'=HYPERLINK" in body


def test_production_refuses_weak_password(make_settings):
    from ugc_engine.config import ConfigError
    s = make_settings(APP_ENV="production", DASHBOARD_PASSWORD="weak")
    with pytest.raises(ConfigError):
        create_app(s)
