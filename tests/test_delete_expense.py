"""Tests for Step 9: Delete expense (GET/POST /expenses/<id>/delete).

Written from .claude/specs/09-delete-expense.md.
"""
import os
import re

import pytest

import database.db as dbmod
from conftest import fetch_all

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"name": "Other Person", "email": "other@example.com", "password": "other123"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEX_RE = re.compile(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b")


# ---------------------------------------------------------------- helpers


def login_demo(client):
    return client.post("/login", data=DEMO)


def demo_id():
    return fetch_all("SELECT id FROM users WHERE email = ?", (DEMO["email"],))[0]["id"]


def make_other_user():
    return dbmod.create_user(OTHER["name"], OTHER["email"], OTHER["password"])


def seed_expense(user_id, amount=50.0, category="Food", date="2026-01-10",
                 description="Original note"):
    return dbmod.create_expense(user_id, amount, category, date, description)


def get_row(expense_id):
    rows = fetch_all("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    return rows[0] if rows else None


def expense_count():
    return fetch_all("SELECT COUNT(*) AS n FROM expenses")[0]["n"]


def delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def own_expense(client):
    login_demo(client)
    return seed_expense(demo_id())


@pytest.fixture
def foreign_expense(app):
    return seed_expense(make_other_user(), description="Foreign note")


# ------------------------------------------------------------- db helper


class TestDbHelper:
    def test_deletes_owned_row_and_returns_true(self, app):
        uid = demo_id()
        eid = seed_expense(uid)
        assert dbmod.delete_expense(eid, uid) is True
        assert get_row(eid) is None

    def test_foreign_row_returns_false_and_stays(self, app):
        eid = seed_expense(demo_id())
        assert dbmod.delete_expense(eid, make_other_user()) is False
        assert get_row(eid) is not None

    def test_missing_row_returns_false(self, app):
        assert dbmod.delete_expense(999999, demo_id()) is False


# ----------------------------------------------------------- signed out


class TestSignedOut:
    def test_get_redirects_to_login(self, client, app):
        eid = seed_expense(demo_id())
        resp = client.get(delete_url(eid))
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_redirects_and_deletes_nothing(self, client, app):
        eid = seed_expense(demo_id())
        resp = client.post(delete_url(eid))
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
        assert get_row(eid) is not None


# ----------------------------------------------------- confirmation page


class TestConfirmPage:
    def test_shows_expense_details(self, client, own_expense):
        resp = client.get(delete_url(own_expense))
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "50.00" in body
        assert "Food" in body
        assert "2026-01-10" in body
        assert "Original note" in body

    def test_has_post_form_and_cancel_link(self, client, own_expense):
        body = client.get(delete_url(own_expense)).get_data(as_text=True)
        assert 'method="POST"' in body
        assert f'action="{delete_url(own_expense)}"' in body
        assert 'href="/profile"' in body

    def test_get_does_not_delete(self, client, own_expense):
        client.get(delete_url(own_expense))
        assert get_row(own_expense) is not None

    def test_profile_has_delete_link(self, client, own_expense):
        body = client.get("/profile").get_data(as_text=True)
        assert f'href="{delete_url(own_expense)}"' in body

    def test_cancel_target_still_lists_expense(self, client, own_expense):
        body = client.get("/profile").get_data(as_text=True)
        assert "Original note" in body


# ---------------------------------------------------------------- delete


class TestDelete:
    def test_post_deletes_and_redirects_to_profile(self, client, own_expense):
        resp = client.post(delete_url(own_expense))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")
        assert get_row(own_expense) is None

    def test_removed_from_profile_list(self, client, own_expense):
        client.post(delete_url(own_expense))
        body = client.get("/profile").get_data(as_text=True)
        assert "Original note" not in body

    def test_only_target_removed(self, client, own_expense):
        other_same_user = seed_expense(demo_id(), description="Keep me")
        before = expense_count()
        client.post(delete_url(own_expense))
        assert expense_count() == before - 1
        assert get_row(other_same_user)["description"] == "Keep me"

    def test_totals_reflect_deletion(self, client, own_expense):
        from database import queries

        uid = demo_id()
        before = queries.get_summary_stats(uid)
        client.post(delete_url(own_expense))
        after = queries.get_summary_stats(uid)
        assert after["total_spent"] == pytest.approx(before["total_spent"] - 50.0)
        assert after["transaction_count"] == before["transaction_count"] - 1

    def test_second_post_is_404(self, client, own_expense):
        assert client.post(delete_url(own_expense)).status_code == 302
        assert client.post(delete_url(own_expense)).status_code == 404

    def test_submitted_user_id_is_ignored(self, client, own_expense):
        resp = client.post(delete_url(own_expense), data={"user_id": "999"})
        assert resp.status_code == 302
        assert get_row(own_expense) is None


# ------------------------------------------------------- 404 / ownership


class TestNotFoundAndOwnership:
    def test_missing_id_404_on_get_and_post(self, client, app):
        login_demo(client)
        assert client.get(delete_url(999999)).status_code == 404
        assert client.post(delete_url(999999)).status_code == 404

    def test_foreign_id_404_on_get_and_post(self, client, app, foreign_expense):
        login_demo(client)
        assert client.get(delete_url(foreign_expense)).status_code == 404
        assert client.post(delete_url(foreign_expense)).status_code == 404
        assert get_row(foreign_expense) is not None

    def test_foreign_post_with_owner_user_id_still_404(self, client, app, foreign_expense):
        login_demo(client)
        owner = get_row(foreign_expense)["user_id"]
        resp = client.post(delete_url(foreign_expense), data={"user_id": str(owner)})
        assert resp.status_code == 404
        assert get_row(foreign_expense) is not None


# ------------------------------------------------------------ regression


class TestRegression:
    def test_add_and_edit_still_work(self, client, own_expense):
        assert client.get("/expenses/add").status_code == 200
        assert client.get(f"/expenses/{own_expense}/edit").status_code == 200


# ---------------------------------------------------------------- assets


class TestAssets:
    @pytest.mark.parametrize("name", ["expense_form.css", "profile.css"])
    def test_css_has_no_hex_literals(self, name):
        assert not HEX_RE.search(read("static", "css", name))

    def test_template_has_no_inline_styles(self):
        html = read("templates", "delete_expense.html")
        assert "style=" not in html and "<style" not in html
        assert "{% extends \"base.html\" %}" in html
