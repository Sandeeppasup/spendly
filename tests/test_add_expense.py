"""Tests for Step 7: Add expense (GET/POST /expenses/add).

Written from .claude/specs/07-add-expense.md.
"""
import os
import re
from datetime import date

import pytest

import database.db as dbmod
from conftest import fetch_all

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"name": "Other Person", "email": "other@example.com", "password": "other123"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEX_RE = re.compile(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b")
ALL_CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
]
ADD_URL = "/expenses/add"


# ---------------------------------------------------------------- helpers


def login(client, **data):
    return client.post("/login", data=data)


def login_demo(client):
    return login(client, **DEMO)


def demo_id():
    return fetch_all("SELECT id FROM users WHERE email = ?", (DEMO["email"],))[0]["id"]


def make_other_user():
    return dbmod.create_user(OTHER["name"], OTHER["email"], OTHER["password"])


def expense_count():
    return fetch_all("SELECT COUNT(*) AS n FROM expenses")[0]["n"]


def valid_form(**overrides):
    data = {
        "amount": "123.45",
        "category": "Food",
        "date": "2026-03-15",
        "description": "Unique test lunch",
    }
    data.update(overrides)
    return data


def post_add(client, **overrides):
    return client.post(ADD_URL, data=valid_form(**overrides))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------- auth guard


class TestAuthGuard:
    def test_get_signed_out_redirects_to_login(self, client):
        resp = client.get(ADD_URL)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_post_signed_out_redirects_to_login_and_inserts_nothing(self, client):
        before = expense_count()
        resp = post_add(client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert expense_count() == before, "Signed-out POST must not insert"

    def test_stale_session_redirects_to_login(self, client):
        with client.session_transaction() as s:
            s["user_id"] = 99999
        before = expense_count()
        resp = post_add(client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert expense_count() == before


# ---------------------------------------------------------------- GET form


class TestGetForm:
    def test_get_signed_in_returns_200_with_form(self, client):
        login_demo(client)
        resp = client.get(ADD_URL)
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "<form" in html
        assert 'method="post"' in html.lower()
        for field in ("amount", "category", "date", "description"):
            assert f'name="{field}"' in html, f"Missing field {field}"

    def test_amount_input_attributes(self, client):
        login_demo(client)
        html = client.get(ADD_URL).data.decode("utf-8")
        assert 'type="number"' in html
        assert 'step="0.01"' in html
        assert 'min="0.01"' in html

    def test_category_select_lists_all_seven_categories(self, client):
        login_demo(client)
        html = client.get(ADD_URL).data.decode("utf-8")
        assert "<select" in html
        for cat in ALL_CATEGORIES:
            assert cat in html, f"Category {cat} missing from select"

    def test_date_defaults_to_today(self, client):
        login_demo(client)
        html = client.get(ADD_URL).data.decode("utf-8")
        assert 'type="date"' in html
        assert date.today().isoformat() in html

    def test_cancel_link_points_to_profile(self, client):
        login_demo(client)
        html = client.get(ADD_URL).data.decode("utf-8")
        assert "Cancel" in html
        assert 'href="/profile"' in html

    def test_get_does_not_insert(self, client):
        login_demo(client)
        before = expense_count()
        client.get(ADD_URL)
        assert expense_count() == before

    def test_form_page_uses_expense_form_css(self, client):
        login_demo(client)
        html = client.get(ADD_URL).data.decode("utf-8")
        assert "expense_form.css" in html


# ------------------------------------------------------------ happy path


class TestSuccess:
    def test_valid_post_redirects_to_profile(self, client):
        login_demo(client)
        resp = post_add(client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

    def test_valid_post_inserts_exactly_one_row_with_values(self, client):
        login_demo(client)
        before = expense_count()
        post_add(client)
        assert expense_count() == before + 1
        rows = fetch_all(
            "SELECT * FROM expenses WHERE description = ?", ("Unique test lunch",)
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["user_id"] == demo_id()
        assert row["amount"] == pytest.approx(123.45)
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-15"

    @pytest.mark.parametrize("category", ALL_CATEGORIES)
    def test_every_category_is_accepted(self, client, category):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, category=category)
        assert resp.status_code == 302
        assert expense_count() == before + 1
        rows = fetch_all(
            "SELECT category FROM expenses WHERE description = ?",
            ("Unique test lunch",),
        )
        assert rows[0]["category"] == category

    @pytest.mark.parametrize(
        "raw,expected", [("50", 50.0), ("0.01", 0.01), ("999.99", 999.99), ("7.5", 7.5)]
    )
    def test_amount_variants_stored_as_float(self, client, raw, expected):
        login_demo(client)
        post_add(client, amount=raw)
        rows = fetch_all(
            "SELECT amount FROM expenses WHERE description = ?", ("Unique test lunch",)
        )
        assert len(rows) == 1
        assert rows[0]["amount"] == pytest.approx(expected)

    def test_amount_rounded_to_two_decimals(self, client):
        login_demo(client)
        post_add(client, amount="12.3456")
        rows = fetch_all(
            "SELECT amount FROM expenses WHERE description = ?", ("Unique test lunch",)
        )
        assert len(rows) == 1
        stored = rows[0]["amount"]
        assert stored == round(stored, 2), "Amount must be rounded to 2 decimals"
        assert abs(stored - 12.35) < 0.011

    def test_description_is_optional_and_stored_empty_or_null(self, client):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, description="")
        assert resp.status_code == 302
        assert expense_count() == before + 1
        row = fetch_all("SELECT description FROM expenses ORDER BY id DESC LIMIT 1")[0]
        assert row["description"] in (None, "")

    def test_description_missing_from_post_is_accepted(self, client):
        login_demo(client)
        before = expense_count()
        data = valid_form()
        del data["description"]
        resp = client.post(ADD_URL, data=data)
        assert resp.status_code == 302
        assert expense_count() == before + 1

    def test_description_is_stripped(self, client):
        login_demo(client)
        post_add(client, description="   padded note   ")
        rows = fetch_all(
            "SELECT description FROM expenses WHERE description LIKE ?", ("%padded note%",)
        )
        assert len(rows) == 1
        assert rows[0]["description"] == "padded note"

    def test_description_of_exactly_200_chars_is_accepted(self, client):
        login_demo(client)
        text = "a" * 200
        before = expense_count()
        resp = post_add(client, description=text)
        assert resp.status_code == 302
        assert expense_count() == before + 1
        row = fetch_all("SELECT description FROM expenses ORDER BY id DESC LIMIT 1")[0]
        assert row["description"] == text

    def test_follow_redirect_lands_on_profile_with_expense_listed(self, client):
        login_demo(client)
        today = date.today().isoformat()
        resp = client.post(
            ADD_URL,
            data=valid_form(date=today, description="Visible new item"),
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Visible new item" in resp.data.decode("utf-8")


# ------------------------------------------------------- profile updates


class TestProfileReflectsNewExpense:
    def test_total_spent_updates(self, client):
        login_demo(client)
        before = client.get("/profile").data.decode("utf-8")
        assert "₹6,939.25" in before  # seeded demo total
        post_add(client, amount="100.00")
        after = client.get("/profile").data.decode("utf-8")
        assert "₹7,039.25" in after, "Total spent should include new expense"

    def test_transaction_count_updates(self, client):
        login_demo(client)
        count_before = fetch_all(
            "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (demo_id(),)
        )[0]["n"]
        post_add(client)
        count_after = fetch_all(
            "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (demo_id(),)
        )[0]["n"]
        assert count_after == count_before + 1
        html = client.get("/profile").data.decode("utf-8")
        assert str(count_after) in html

    def test_category_breakdown_includes_new_category_amount(self, client):
        login_demo(client)
        post_add(client, category="Health", amount="5000.00")
        html = client.get("/profile").data.decode("utf-8")
        assert "Health" in html
        assert "5,000" in html or "5000" in html

    def test_new_expense_visible_in_transaction_list(self, client):
        login_demo(client)
        today = date.today().isoformat()
        post_add(client, date=today, description="Brand new purchase")
        html = client.get("/profile").data.decode("utf-8")
        assert "Brand new purchase" in html

    def test_new_expense_respects_date_filter(self, client):
        login_demo(client)
        post_add(client, date="2020-01-10", description="Old filtered purchase")
        inside = client.get("/profile?start=2020-01-01&end=2020-01-31").data.decode("utf-8")
        outside = client.get("/profile?start=2021-01-01&end=2021-01-31").data.decode("utf-8")
        assert "Old filtered purchase" in inside
        assert "Old filtered purchase" not in outside


# ----------------------------------------------------------- validation


class TestAmountValidation:
    @pytest.mark.parametrize(
        "bad",
        ["", "   ", "0", "0.00", "-5", "-0.01", "abc", "12abc", "nan", "NaN",
         "inf", "-inf", "Infinity", "1e999", "1e20"],
    )
    def test_bad_amount_shows_error_and_inserts_nothing(self, client, bad):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, amount=bad)
        assert resp.status_code == 200, f"amount={bad!r} should re-render form"
        assert b'name="amount"' in resp.data
        assert expense_count() == before, f"amount={bad!r} must not insert"

    def test_missing_amount_field_rejected(self, client):
        login_demo(client)
        before = expense_count()
        data = valid_form()
        del data["amount"]
        resp = client.post(ADD_URL, data=data)
        assert resp.status_code == 200
        assert expense_count() == before

    def test_error_message_is_displayed(self, client):
        login_demo(client)
        bad_html = post_add(client, amount="-5").data.decode("utf-8")
        assert 'role="alert"' in bad_html
        assert "Amount must be greater than 0." in bad_html


class TestCategoryValidation:
    @pytest.mark.parametrize(
        "bad", ["", "Gambling", "food", "FOOD", "<script>", "1", "Food; DROP TABLE expenses"]
    )
    def test_bad_category_shows_error_and_inserts_nothing(self, client, bad):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, category=bad)
        assert resp.status_code == 200
        assert expense_count() == before, f"category={bad!r} must not insert"

    def test_missing_category_field_rejected(self, client):
        login_demo(client)
        before = expense_count()
        data = valid_form()
        del data["category"]
        resp = client.post(ADD_URL, data=data)
        assert resp.status_code == 200
        assert expense_count() == before


class TestDateValidation:
    @pytest.mark.parametrize(
        "bad",
        ["", "not-a-date", "2026-02-31", "2026-13-01", "2026-00-10", "2026-04-31",
         "2025-02-29", "15/03/2026", "2026/03/15", "20260315", "2026-3-5x"],
    )
    def test_bad_date_shows_error_and_inserts_nothing(self, client, bad):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, date=bad)
        assert resp.status_code == 200
        assert expense_count() == before, f"date={bad!r} must not insert"

    def test_leap_day_is_accepted(self, client):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, date="2024-02-29")
        assert resp.status_code == 302
        assert expense_count() == before + 1

    def test_missing_date_field_rejected(self, client):
        login_demo(client)
        before = expense_count()
        data = valid_form()
        del data["date"]
        resp = client.post(ADD_URL, data=data)
        assert resp.status_code == 200
        assert expense_count() == before


class TestDescriptionValidation:
    @pytest.mark.parametrize("length", [201, 500, 5000])
    def test_description_over_200_chars_rejected(self, client, length):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, description="x" * length)
        assert resp.status_code == 200
        assert expense_count() == before

    def test_description_over_limit_only_after_strip_is_accepted(self, client):
        login_demo(client)
        before = expense_count()
        resp = post_add(client, description="  " + "y" * 200 + "  ")
        assert resp.status_code == 302
        assert expense_count() == before + 1


# ------------------------------------------------------ preserved values


class TestPreservedValues:
    def test_values_preserved_after_amount_failure(self, client):
        login_demo(client)
        resp = post_add(
            client, amount="-5", category="Transport", date="2026-04-02",
            description="Keep this text",
        )
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "Keep this text" in html
        assert "2026-04-02" in html
        assert "-5" in html
        # the chosen category should be the selected option
        assert re.search(r'<option[^>]*value="Transport"[^>]*selected', html), (
            "Transport should remain selected"
        )

    def test_values_preserved_after_date_failure(self, client):
        login_demo(client)
        resp = post_add(
            client, date="2026-02-31", amount="42.50", category="Bills",
            description="Electric bill",
        )
        html = resp.data.decode("utf-8")
        assert "42.50" in html
        assert "Electric bill" in html
        assert "2026-02-31" in html or date.today().isoformat() in html
        assert re.search(r'<option[^>]*value="Bills"[^>]*selected', html)

    def test_values_preserved_after_description_failure(self, client):
        login_demo(client)
        long_text = "z" * 250
        resp = post_add(client, description=long_text, amount="9.99")
        html = resp.data.decode("utf-8")
        assert "9.99" in html
        assert long_text in html

    def test_preserved_description_is_html_escaped(self, client):
        login_demo(client)
        resp = post_add(client, amount="-1", description="<script>alert(1)</script>")
        html = resp.data.decode("utf-8")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


# --------------------------------------------------- security / isolation


class TestSecurityAndIsolation:
    def test_posted_user_id_is_ignored(self, client):
        other_id = make_other_user()
        login_demo(client)
        post_add(client, user_id=str(other_id), description="Spoof attempt")
        rows = fetch_all(
            "SELECT user_id FROM expenses WHERE description = ?", ("Spoof attempt",)
        )
        assert len(rows) == 1
        assert rows[0]["user_id"] == demo_id()
        assert rows[0]["user_id"] != other_id

    def test_posted_nonexistent_user_id_is_ignored(self, client):
        login_demo(client)
        resp = post_add(client, user_id="99999", description="Ghost attempt")
        assert resp.status_code == 302
        rows = fetch_all(
            "SELECT user_id FROM expenses WHERE description = ?", ("Ghost attempt",)
        )
        assert rows[0]["user_id"] == demo_id()

    def test_sql_injection_in_description_stored_verbatim(self, client):
        login_demo(client)
        payload = "x'); DROP TABLE expenses; --"
        before = expense_count()
        resp = post_add(client, description=payload)
        assert resp.status_code == 302
        assert expense_count() == before + 1, "expenses table must still work"
        rows = fetch_all("SELECT description FROM expenses ORDER BY id DESC LIMIT 1")
        assert rows[0]["description"] == payload
        assert client.get("/profile").status_code == 200

    def test_sql_injection_or_clause_in_description(self, client):
        login_demo(client)
        payload = "' OR '1'='1"
        post_add(client, description=payload)
        rows = fetch_all("SELECT description FROM expenses WHERE description = ?", (payload,))
        assert len(rows) == 1

    def test_expense_not_visible_to_other_user(self, client):
        make_other_user()
        login_demo(client)
        post_add(client, date=date.today().isoformat(), description="Private demo item")
        client.get("/logout")
        login(client, email=OTHER["email"], password=OTHER["password"])
        html = client.get("/profile").data.decode("utf-8")
        assert "Private demo item" not in html

    def test_other_user_expense_belongs_to_other_user(self, client):
        other_id = make_other_user()
        login(client, email=OTHER["email"], password=OTHER["password"])
        post_add(client, description="Other's item")
        rows = fetch_all(
            "SELECT user_id FROM expenses WHERE description = ?", ("Other's item",)
        )
        assert len(rows) == 1
        assert rows[0]["user_id"] == other_id

    def test_other_users_expense_not_added_to_demo_totals(self, client):
        make_other_user()
        login(client, email=OTHER["email"], password=OTHER["password"])
        post_add(client, amount="1000.00")
        client.get("/logout")
        login_demo(client)
        html = client.get("/profile").data.decode("utf-8")
        assert "₹6,939.25" in html


# ------------------------------------------------------ profile page link


class TestProfileLink:
    def test_profile_has_add_expense_link(self, client):
        login_demo(client)
        html = client.get("/profile").data.decode("utf-8")
        assert "Add expense" in html
        assert f'href="{ADD_URL}"' in html

    def test_profile_empty_state_points_to_add_expense(self, client):
        make_other_user()
        login(client, email=OTHER["email"], password=OTHER["password"])
        html = client.get("/profile").data.decode("utf-8")
        assert f'href="{ADD_URL}"' in html
        assert "Add expense" in html or "add" in html.lower()


# ------------------------------------------------------------- stubs


class TestStubsUnchanged:
    def test_stubs_do_not_modify_expenses(self, client):
        login_demo(client)
        before = expense_count()
        client.get("/expenses/1/delete")
        assert expense_count() == before


# ------------------------------------------------------- static assets


class TestAssets:
    def test_expense_form_css_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "static", "css", "expense_form.css"))

    def test_expense_form_css_has_no_hardcoded_hex_colours(self):
        css = read("static", "css", "expense_form.css")
        matches = HEX_RE.findall(css)
        assert not matches, f"Hardcoded hex colours found: {matches}"

    def test_add_expense_template_has_no_hardcoded_urls_or_inline_styles(self):
        src = read("templates", "add_expense.html")
        assert 'action="/' not in src
        assert 'href="/' not in src
        assert "<style" not in src
        assert 'style="' not in src

    def test_add_expense_template_extends_base(self):
        src = read("templates", "add_expense.html")
        assert "{% extends" in src and "base.html" in src
