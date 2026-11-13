"""Tests for Step 8: Edit expense (GET/POST /expenses/<id>/edit).

Written from .claude/specs/08-edit-expense.md.
"""
import os
import re

import pytest

import database.db as dbmod
from database import queries
from conftest import fetch_all

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"name": "Other Person", "email": "other@example.com", "password": "other123"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEX_RE = re.compile(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b")


# ---------------------------------------------------------------- helpers


def login(client, **data):
    return client.post("/login", data=data)


def login_demo(client):
    return login(client, **DEMO)


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


def valid_form(**overrides):
    data = {
        "amount": "99.50",
        "category": "Transport",
        "date": "2026-02-20",
        "description": "Edited note",
    }
    data.update(overrides)
    return data


def edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def own_expense(client):
    """Log in as demo and return the id of a fresh expense owned by demo."""
    login_demo(client)
    return seed_expense(demo_id())


@pytest.fixture
def foreign_expense(app):
    """An expense owned by a different user (not demo)."""
    return seed_expense(make_other_user(), description="Foreign note")


# ------------------------------------------------------------- db helpers


class TestDbHelpers:
    def test_get_expense_returns_row_for_owner(self, app):
        uid = demo_id()
        eid = seed_expense(uid)
        row = dbmod.get_expense(eid, uid)
        assert row is not None
        assert row["id"] == eid and row["description"] == "Original note"

    def test_get_expense_none_for_other_user(self, app):
        eid = seed_expense(demo_id())
        assert dbmod.get_expense(eid, make_other_user()) is None

    def test_get_expense_none_for_missing_id(self, app):
        assert dbmod.get_expense(999999, demo_id()) is None

    def test_update_expense_changes_fields_and_returns_true(self, app):
        uid = demo_id()
        eid = seed_expense(uid)
        before = get_row(eid)
        assert dbmod.update_expense(eid, uid, 12.5, "Bills", "2026-05-05", "New") is True
        row = get_row(eid)
        assert (row["amount"], row["category"], row["date"], row["description"]) == (
            12.5, "Bills", "2026-05-05", "New",
        )
        assert row["user_id"] == uid
        assert row["created_at"] == before["created_at"]

    def test_update_expense_wrong_user_returns_false_and_unchanged(self, app):
        eid = seed_expense(demo_id())
        other = make_other_user()
        assert dbmod.update_expense(eid, other, 1.0, "Other", "2026-05-05", "x") is False
        row = get_row(eid)
        assert row["amount"] == 50.0 and row["description"] == "Original note"

    def test_update_expense_missing_id_returns_false(self, app):
        assert dbmod.update_expense(999999, demo_id(), 1.0, "Other", "2026-05-05", "x") is False

    def test_update_expense_does_not_add_rows(self, app):
        uid = demo_id()
        eid = seed_expense(uid)
        before = expense_count()
        dbmod.update_expense(eid, uid, 1.0, "Other", "2026-05-05", "x")
        assert expense_count() == before

    def test_update_expense_sql_injection_stored_verbatim(self, app):
        uid = demo_id()
        eid = seed_expense(uid)
        evil = "x'); DROP TABLE expenses;--"
        dbmod.update_expense(eid, uid, 1.0, "Other", "2026-05-05", evil)
        assert get_row(eid)["description"] == evil


# ------------------------------------------------------------------- auth


class TestAuth:
    def test_get_signed_out_redirects_to_login(self, client, app):
        eid = seed_expense(demo_id())
        resp = client.get(edit_url(eid))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_post_signed_out_redirects_and_changes_nothing(self, client, app):
        eid = seed_expense(demo_id())
        resp = client.post(edit_url(eid), data=valid_form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert get_row(eid)["description"] == "Original note"

    def test_stale_session_redirects_to_login(self, client, app):
        eid = seed_expense(demo_id())
        with client.session_transaction() as s:
            s["user_id"] = 99999
        resp = client.get(edit_url(eid))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")


# -------------------------------------------------------------------- GET


class TestGetForm:
    def test_get_returns_200_and_prefilled_values(self, client, own_expense):
        html = client.get(edit_url(own_expense)).data.decode("utf-8")
        assert 'value="50.00"' in html
        assert 'value="2026-01-10"' in html
        assert 'value="Original note"' in html
        assert re.search(r'<option[^>]*value="Food"[^>]*selected', html)

    def test_form_posts_to_edit_url_and_has_labels(self, client, own_expense):
        html = client.get(edit_url(own_expense)).data.decode("utf-8")
        assert f'action="{edit_url(own_expense)}"' in html
        assert "Edit expense" in html
        assert "Save changes" in html
        assert "₹" in html

    def test_cancel_link_points_to_profile(self, client, own_expense):
        html = client.get(edit_url(own_expense)).data.decode("utf-8")
        assert 'href="/profile"' in html

    def test_null_description_renders_empty(self, client, app):
        login_demo(client)
        eid = seed_expense(demo_id(), description=None)
        html = client.get(edit_url(eid)).data.decode("utf-8")
        assert 'name="description"' in html and "None" not in html

    def test_get_does_not_modify(self, client, own_expense):
        client.get(edit_url(own_expense))
        assert get_row(own_expense)["description"] == "Original note"


# ------------------------------------------------------------- ownership


class TestOwnership404:
    def test_missing_id_get_and_post_404(self, client, app):
        login_demo(client)
        assert client.get(edit_url(999999)).status_code == 404
        assert client.post(edit_url(999999), data=valid_form()).status_code == 404

    def test_foreign_id_get_404(self, client, foreign_expense):
        login_demo(client)
        assert client.get(edit_url(foreign_expense)).status_code == 404

    def test_foreign_id_post_404_and_unchanged(self, client, foreign_expense):
        login_demo(client)
        resp = client.post(edit_url(foreign_expense), data=valid_form())
        assert resp.status_code == 404
        row = get_row(foreign_expense)
        assert row["description"] == "Foreign note" and row["amount"] == 50.0

    def test_foreign_id_invalid_post_still_404(self, client, foreign_expense):
        login_demo(client)
        resp = client.post(edit_url(foreign_expense), data=valid_form(amount="abc"))
        assert resp.status_code == 404

    def test_foreign_and_missing_responses_identical(self, client, foreign_expense):
        login_demo(client)
        a = client.get(edit_url(foreign_expense))
        b = client.get(edit_url(999999))
        assert a.status_code == b.status_code == 404
        assert a.data == b.data


# ---------------------------------------------------------------- success


class TestSuccess:
    def test_valid_post_redirects_to_profile(self, client, own_expense):
        resp = client.post(edit_url(own_expense), data=valid_form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

    def test_db_updated_and_count_unchanged(self, client, own_expense):
        before = expense_count()
        client.post(edit_url(own_expense), data=valid_form())
        row = get_row(own_expense)
        assert (row["amount"], row["category"], row["date"], row["description"]) == (
            99.5, "Transport", "2026-02-20", "Edited note",
        )
        assert expense_count() == before

    def test_profile_shows_updated_values(self, client, own_expense):
        client.post(edit_url(own_expense), data=valid_form(description="Zebra edit"))
        html = client.get("/profile").data.decode("utf-8")
        assert "Zebra edit" in html
        assert "Original note" not in html

    def test_totals_reflect_edit(self, client, app):
        login_demo(client)
        uid = demo_id()
        eid = seed_expense(uid, amount=50.0)
        total_before = queries.get_summary_stats(uid)["total_spent"]
        client.post(edit_url(eid), data=valid_form(amount="150.00"))
        total_after = queries.get_summary_stats(uid)["total_spent"]
        assert round(total_after - total_before, 2) == 100.0

    def test_clearing_description_saves(self, client, own_expense):
        resp = client.post(edit_url(own_expense), data=valid_form(description=""))
        assert resp.status_code == 302
        assert (get_row(own_expense)["description"] or "") == ""

    def test_posted_user_id_is_ignored(self, client, own_expense):
        other = make_other_user()
        client.post(edit_url(own_expense), data=valid_form(user_id=str(other)))
        assert get_row(own_expense)["user_id"] == demo_id()

    def test_sql_injection_in_description_stored_verbatim(self, client, own_expense):
        evil = "x'); DROP TABLE expenses;--"
        client.post(edit_url(own_expense), data=valid_form(description=evil))
        assert get_row(own_expense)["description"] == evil
        assert expense_count() > 0


# ------------------------------------------------------------- validation


class TestValidationFailure:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"amount": ""},
            {"amount": "0"},
            {"amount": "-5"},
            {"amount": "abc"},
            {"amount": "nan"},
            {"amount": "inf"},
            {"category": "Nope"},
            {"category": ""},
            {"date": "not-a-date"},
            {"date": "2026-02-31"},
            {"date": ""},
            {"description": "x" * 201},
        ],
    )
    def test_bad_input_shows_error_and_changes_nothing(self, client, own_expense, overrides):
        resp = client.post(edit_url(own_expense), data=valid_form(**overrides))
        assert resp.status_code == 200
        assert 'role="alert"' in resp.data.decode("utf-8")
        row = get_row(own_expense)
        assert row["amount"] == 50.0 and row["description"] == "Original note"
        assert row["category"] == "Food" and row["date"] == "2026-01-10"

    def test_submitted_values_kept_not_stored_ones(self, client, own_expense):
        resp = client.post(
            edit_url(own_expense),
            data=valid_form(amount="abc", description="Submitted desc"),
        )
        html = resp.data.decode("utf-8")
        assert 'value="Submitted desc"' in html
        assert 'value="Original note"' not in html


# ------------------------------------------------------------ profile UI


class TestProfileLinks:
    def test_transactions_include_id(self, app):
        uid = demo_id()
        txns = queries.get_recent_transactions(uid)
        assert txns and all("id" in t for t in txns)

    def test_each_row_has_edit_link(self, client, app):
        login_demo(client)
        html = client.get("/profile").data.decode("utf-8")
        for t in queries.get_recent_transactions(demo_id()):
            assert f'href="/expenses/{t["id"]}/edit"' in html

    def test_no_edit_links_for_other_users_rows(self, client, foreign_expense):
        login_demo(client)
        html = client.get("/profile").data.decode("utf-8")
        assert f'href="/expenses/{foreign_expense}/edit"' not in html

    def test_empty_state_colspan_is_five(self, client, app):
        make_other_user()
        login(client, email=OTHER["email"], password=OTHER["password"])
        html = client.get("/profile").data.decode("utf-8")
        assert 'colspan="5"' in html


# ------------------------------------------------------ assets/regression


class TestHygiene:
    def test_edit_template_has_no_inline_styles_or_hardcoded_urls(self):
        src = read("templates", "edit_expense.html")
        assert "<style" not in src and 'style="' not in src
        assert 'action="/' not in src and 'href="/' not in src

    def test_edit_template_extends_base_and_uses_expense_form_css(self):
        src = read("templates", "edit_expense.html")
        assert "{% extends" in src and "base.html" in src
        assert "expense_form.css" in src

    def test_profile_css_has_no_hardcoded_hex_colours(self):
        assert not HEX_RE.findall(read("static", "css", "profile.css"))


class TestRegression:
    def test_add_expense_still_works(self, client, app):
        login_demo(client)
        resp = client.post(
            "/expenses/add",
            data={"amount": "10", "category": "Food", "date": "2026-03-01", "description": "x"},
        )
        assert resp.status_code == 302

    def test_delete_route_is_still_stub(self, client):
        resp = client.get("/expenses/1/delete")
        assert resp.status_code == 200
        assert b"Step 9" in resp.data
