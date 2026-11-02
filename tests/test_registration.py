import os

import pytest
from werkzeug.security import check_password_hash

import database.db as dbmod
from conftest import fetch_all

VALID = {"name": "Asha Rao", "email": "asha@example.com", "password": "password123"}


def user_count():
    return fetch_all("SELECT COUNT(*) AS c FROM users")[0]["c"]


def test_get_register_200(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b'name="email"' in resp.data


def test_valid_post_creates_user_and_redirects(client):
    before = user_count()
    resp = client.post("/register", data=VALID)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert user_count() == before + 1


def test_password_is_hashed(client):
    client.post("/register", data=VALID)
    row = fetch_all("SELECT password_hash FROM users WHERE email = ?", (VALID["email"],))[0]
    assert row["password_hash"] != VALID["password"]
    assert check_password_hash(row["password_hash"], VALID["password"])


def test_email_trimmed_and_lowercased(client):
    client.post("/register", data={**VALID, "email": "  Foo@Example.COM "})
    rows = fetch_all("SELECT email FROM users WHERE email = ?", ("foo@example.com",))
    assert len(rows) == 1


def test_duplicate_email_any_case(client):
    client.post("/register", data=VALID)
    before = user_count()
    resp = client.post("/register", data={**VALID, "email": "ASHA@Example.com"})
    assert resp.status_code == 200
    assert b"An account with that email already exists." in resp.data
    assert user_count() == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"email": "noatsign"},
        {"email": "@x.com"},
        {"email": "a@"},
        {"password": "1234567"},
    ],
)
def test_validation_errors_create_no_row(client, overrides):
    before = user_count()
    resp = client.post("/register", data={**VALID, **overrides})
    assert resp.status_code == 200
    assert b"auth-error" in resp.data
    assert user_count() == before


def test_failed_submit_repopulates_name_email_not_password(client):
    resp = client.post("/register", data={**VALID, "password": "short"})
    html = resp.data.decode()
    assert 'value="Asha Rao"' in html
    assert 'value="asha@example.com"' in html
    assert "short" not in html


def test_template_has_no_hardcoded_urls():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "register.html")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert 'action="/' not in src
    assert 'href="/' not in src


def test_demo_user_intact_and_seed_idempotent(client, app):
    client.post("/register", data=VALID)
    demo = fetch_all("SELECT id FROM users WHERE email = ?", ("demo@spendly.com",))
    assert len(demo) == 1
    users_before = user_count()
    expenses_before = fetch_all("SELECT COUNT(*) AS c FROM expenses")[0]["c"]
    dbmod.seed_db()
    assert user_count() == users_before
    assert fetch_all("SELECT COUNT(*) AS c FROM expenses")[0]["c"] == expenses_before


def test_post_does_not_create_session(client):
    resp = client.post("/register", data=VALID)
    assert "Set-Cookie" not in resp.headers
