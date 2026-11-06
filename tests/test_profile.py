import os
import re

from conftest import fetch_all  # noqa: F401  (keeps conftest import ordering)

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEX_RE = re.compile(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b")


def login(client, **data):
    return client.post("/login", data=data)


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ auth


def test_profile_redirects_when_logged_out(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_redirects_with_stale_session(client):
    with client.session_transaction() as s:
        s["user_id"] = 99999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# --------------------------------------------------------------- content


def test_profile_200_when_logged_in(client):
    login(client, **DEMO)
    assert client.get("/profile").status_code == 200


def test_profile_shows_user_info(client):
    login(client, **DEMO)
    html = client.get("/profile").data
    assert b"Demo User" in html
    assert b"demo@spendly.com" in html
    assert b"DU" in html


def test_profile_navbar_logged_in_state(client):
    login(client, **DEMO)
    html = client.get("/profile").data
    assert b"Sign out" in html
    assert b"Get started" not in html
    assert b'href="/profile"' in html


def test_profile_has_stats_table_and_breakdown(client):
    login(client, **DEMO)
    html = client.get("/profile").data.decode("utf-8")
    for label in ("Total spent", "Transactions", "Top category"):
        assert label in html
    body = html.split("<tbody>")[1].split("</tbody>")[0]
    assert body.count("<tr>") >= 3
    assert html.count("profile-badge ") >= 3
    assert html.count("profile-breakdown-item") >= 3


# ------------------------------------------------------- template hygiene


def test_profile_template_has_no_hex_colours():
    assert not HEX_RE.search(read("templates", "profile.html"))


def test_profile_css_has_no_hex_colours():
    assert not HEX_RE.search(read("static", "css", "profile.css"))


def test_profile_template_has_no_inline_styles():
    assert "style=" not in read("templates", "profile.html")


def test_profile_template_has_no_hardcoded_urls():
    src = read("templates", "profile.html")
    assert 'href="/' not in src
    assert 'src="/' not in src


def test_profile_template_extends_base_and_links_css():
    src = read("templates", "profile.html")
    assert '{% extends "base.html" %}' in src
    assert "url_for('static', filename='css/profile.css')" in src
