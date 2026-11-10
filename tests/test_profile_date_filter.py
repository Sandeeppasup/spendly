"""Tests for Step 6: date filter on the /profile page (see
.claude/specs/06-date-filter-profile-page.md).

Written from the spec, not the implementation.
"""
import inspect
import os
import re
from datetime import date, timedelta

import pytest

import database.db as dbmod
from conftest import fetch_all
from database import queries

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"email": "other@example.com", "password": "password123"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ERROR_MARK = "profile-filter-error"
NOTE_MARK = "profile-filter-note"

TODAY = date.today()
MONTH_START = TODAY.replace(day=1)


# ---------------------------------------------------------------- helpers


def login(client, **data):
    return client.post("/login", data=data)


def demo_id():
    return fetch_all("SELECT id FROM users WHERE email = 'demo@spendly.com'")[0]["id"]


def make_user(email=OTHER["email"], password=OTHER["password"]):
    return dbmod.create_user("Other Person", email, password)


def add_expense(user_id, amount, category, iso, description="x"):
    conn = dbmod.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, iso, description),
        )
        conn.commit()
    finally:
        conn.close()


def get_page(client, **params):
    resp = client.get("/profile", query_string=params)
    return resp, resp.data.decode("utf-8")


def preset_links(html):
    """Return {label: (href, tag_html)} for links in the quick-range nav."""
    # Scope to the quick-range nav: base.html has its own site <nav> first.
    nav = re.search(r'<nav[^>]*profile-presets[^>]*>(.*?)</nav>', html, re.S)
    assert nav, "Expected a preset navigation block on the profile page"
    found = {}
    for m in re.finditer(r"<a\b([^>]*)>\s*([^<]+?)\s*</a>", nav.group(1)):
        attrs, label = m.group(1), m.group(2)
        href = re.search(r'href="([^"]*)"', attrs).group(1)
        found[label] = (href.replace("&amp;", "&"), attrs)
    return found


@pytest.fixture
def user(app):
    """Fresh user with a known set of expenses on fixed dates."""
    uid = make_user()
    add_expense(uid, 100.00, "Food", "2026-03-01", "edge-start")
    add_expense(uid, 200.50, "Transport", "2026-03-10", "middle")
    add_expense(uid, 50.25, "Food", "2026-03-31", "edge-end")
    add_expense(uid, 999.00, "Bills", "2026-02-28", "before-range")
    add_expense(uid, 777.00, "Health", "2026-04-01", "after-range")
    return uid


@pytest.fixture
def user_client(client, user):
    login(client, **OTHER)
    return client


@pytest.fixture
def demo_client(client):
    login(client, **DEMO)
    return client


# ------------------------------------------------------------- auth guard


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-01-01"},
        {"end": "2026-12-31"},
        {"start": "2026-01-01", "end": "2026-12-31"},
        {"start": "garbage"},
    ],
)
def test_signed_out_filtered_profile_redirects_to_login(client, params):
    resp = client.get("/profile", query_string=params)
    assert resp.status_code == 302, "Signed-out visit should redirect"
    assert resp.headers["Location"].endswith("/login")


# ------------------------------------------------- unfiltered (baseline)


def test_no_params_shows_all_time_demo_totals(demo_client):
    resp, html = get_page(demo_client)
    assert resp.status_code == 200
    assert "₹6,939.25" in html
    assert ERROR_MARK not in html, "No error expected without params"
    assert NOTE_MARK not in html, "No range note expected when unfiltered"


def test_no_params_demo_has_eight_transactions(app):
    stats = queries.get_summary_stats(demo_id())
    assert stats["transaction_count"] == 8
    assert stats["total_spent"] == 6939.25


# ------------------------------------------------------------ filter bar


def test_filter_bar_has_date_inputs_apply_and_clear(demo_client):
    _, html = get_page(demo_client)
    assert re.search(r'<input[^>]*type="date"[^>]*name="start"', html), "From input"
    assert re.search(r'<input[^>]*type="date"[^>]*name="end"', html), "To input"
    assert "Apply" in html
    assert "Clear" in html
    form = re.search(r"<form[^>]*>", html[html.index('name="start"') - 600 :])
    assert form and "get" in form.group(0).lower(), "Filter form should use GET"


def test_filter_inputs_are_prefilled_with_active_values(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    assert re.search(r'name="start"[^>]*value="2026-03-01"', html)
    assert re.search(r'name="end"[^>]*value="2026-03-31"', html)


def test_filter_inputs_empty_when_unfiltered(user_client):
    _, html = get_page(user_client)
    assert not re.search(r'name="start"[^>]*value="\d', html)
    assert not re.search(r'name="end"[^>]*value="\d', html)


def test_clear_link_points_to_plain_profile(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    clear = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*Clear\s*</a>', html)
    assert clear, "Expected a Clear link"
    assert clear.group(1) == "/profile"


def test_clear_returns_to_unfiltered_view(user_client):
    _, filtered = get_page(user_client, start="2026-03-01", end="2026-03-31")
    assert "before-range" not in filtered
    resp, html = get_page(user_client)
    assert "before-range" in html and "after-range" in html
    assert NOTE_MARK not in html


# -------------------------------------------------- range filtering


def test_range_filters_transactions_inclusively(user_client):
    resp, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    assert resp.status_code == 200
    for desc in ("edge-start", "middle", "edge-end"):
        assert desc in html, f"{desc} should be in range (inclusive bounds)"
    for desc in ("before-range", "after-range"):
        assert desc not in html, f"{desc} should be excluded"


def test_range_scopes_summary_stats(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    # 100.00 + 200.50 + 50.25
    assert "₹350.75" in html
    assert "₹2,126.75" not in html, "All-time total must not appear"


def test_range_scopes_category_breakdown(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    assert html.count("profile-breakdown-item") == 2, "Food and Transport only"


def test_range_top_category_reflects_range(user_client):
    # In range: Food 150.25 vs Transport 200.50 -> Transport on top.
    # All-time Bills (999) would be top, Health (777) second.
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    assert "Transport" in html
    assert "Bills" not in html.split("Top category")[1].split("</div>")[0]


def test_single_day_range_is_inclusive_both_ends(user_client):
    _, html = get_page(user_client, start="2026-03-10", end="2026-03-10")
    assert "middle" in html
    assert "edge-start" not in html and "edge-end" not in html
    assert "₹200.50" in html


def test_start_only_is_open_ended_upwards(user_client):
    _, html = get_page(user_client, start="2026-03-31")
    assert "edge-end" in html and "after-range" in html
    assert "edge-start" not in html and "before-range" not in html
    assert ERROR_MARK not in html


def test_end_only_is_open_ended_downwards(user_client):
    _, html = get_page(user_client, end="2026-03-01")
    assert "edge-start" in html and "before-range" in html
    assert "middle" not in html and "after-range" not in html
    assert ERROR_MARK not in html


def test_start_equals_end_is_not_reversed(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-01")
    assert ERROR_MARK not in html
    assert "edge-start" in html


def test_range_note_shown_when_filter_active(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    assert NOTE_MARK in html
    assert "01 Mar 2026" in html and "31 Mar 2026" in html


def test_demo_full_month_range_matches_all_time(demo_client):
    start = MONTH_START.isoformat()
    end = (MONTH_START + timedelta(days=27)).isoformat()
    _, html = get_page(demo_client, start=start, end=end)
    assert "₹6,939.25" in html
    assert html.count("profile-breakdown-item") == 7


def test_demo_range_in_far_past_is_empty(demo_client):
    _, html = get_page(demo_client, start="1999-01-01", end="1999-12-31")
    assert "₹0.00" in html
    assert "₹6,939.25" not in html


# ------------------------------------------------------------ empty range


def test_empty_range_shows_zero_and_filtered_empty_state(user_client):
    resp, html = get_page(user_client, start="2020-01-01", end="2020-01-31")
    assert resp.status_code == 200
    assert "₹0.00" in html
    assert "No expenses in this period." in html
    assert "No expenses yet." not in html
    assert html.count("profile-breakdown-item") == 0
    assert ERROR_MARK not in html, "An empty range is not an error"


def test_unfiltered_empty_user_keeps_original_empty_text(client, app):
    make_user()
    login(client, **OTHER)
    _, html = get_page(client)
    assert "No expenses yet." in html
    assert "No expenses in this period." not in html


# ------------------------------------------------------------ validation


@pytest.mark.parametrize(
    "params",
    [
        {"start": "garbage"},
        {"end": "garbage"},
        {"start": "garbage", "end": "also-bad"},
        {"end": "2026-02-31"},
        {"start": "2026-02-31"},
        {"start": "2026-13-01"},
        {"start": "03/01/2026"},
        {"start": "2026-3-1x"},
        {"start": "' OR 1=1 --"},
        {"end": "'; DROP TABLE expenses; --"},
        {"start": "2026-01-01' OR '1'='1"},
    ],
)
def test_invalid_dates_show_inline_error_and_no_500(user_client, params):
    resp, html = get_page(user_client, **params)
    assert resp.status_code == 200, f"Expected 200 for {params}, got {resp.status_code}"
    assert ERROR_MARK in html, f"Expected inline error for {params}"


@pytest.mark.parametrize(
    "params",
    [{"start": "' OR 1=1 --"}, {"end": "2026-02-31"}, {"start": "garbage"}],
)
def test_invalid_single_param_falls_back_to_all_time(user_client, params):
    _, html = get_page(user_client, **params)
    for desc in ("edge-start", "middle", "edge-end", "before-range", "after-range"):
        assert desc in html, f"{desc} should show (invalid date treated as absent)"


def test_invalid_start_with_valid_end_still_applies_end(user_client):
    _, html = get_page(user_client, start="garbage", end="2026-03-01")
    assert ERROR_MARK in html
    assert "after-range" not in html, "Valid end should still scope results"
    assert "edge-start" in html


def test_sql_injection_does_not_damage_data(user_client):
    get_page(user_client, start="'; DROP TABLE expenses; --")
    rows = fetch_all("SELECT COUNT(*) AS n FROM expenses")
    assert rows[0]["n"] >= 5, "expenses table must be intact"


def test_sql_injection_does_not_leak_other_users(user_client):
    _, html = get_page(user_client, start="' OR 1=1 --")
    assert "Lunch with friends" not in html, "Demo user's data must not leak"


def test_reversed_range_shows_error_and_unfiltered_view(user_client):
    resp, html = get_page(user_client, start="2026-03-31", end="2026-03-01")
    assert resp.status_code == 200
    assert ERROR_MARK in html
    for desc in ("edge-start", "middle", "edge-end", "before-range", "after-range"):
        assert desc in html, "Reversed range falls back to unfiltered view"


def test_reversed_range_from_spec_example(demo_client):
    resp, html = get_page(demo_client, start="2026-11-10", end="2026-11-01")
    assert resp.status_code == 200
    assert ERROR_MARK in html
    assert "₹6,939.25" in html


def test_error_message_is_escaped(user_client):
    _, html = get_page(user_client, start="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html


# ---------------------------------------------------------- blank params


@pytest.mark.parametrize(
    "params",
    [
        {"start": "", "end": ""},
        {"start": ""},
        {"end": ""},
    ],
)
def test_blank_params_treated_as_absent_without_error(user_client, params):
    resp, html = get_page(user_client, **params)
    assert resp.status_code == 200
    assert ERROR_MARK not in html, "Blank params must not raise an error"
    assert "before-range" in html and "after-range" in html


def test_blank_start_with_valid_end_is_open_ended(user_client):
    _, html = get_page(user_client, start="", end="2026-03-01")
    assert ERROR_MARK not in html
    assert "edge-start" in html and "before-range" in html
    assert "middle" not in html


def test_blank_end_with_valid_start_is_open_ended(user_client):
    _, html = get_page(user_client, start="2026-03-31", end="")
    assert ERROR_MARK not in html
    assert "edge-end" in html and "after-range" in html
    assert "middle" not in html


# --------------------------------------------------------------- presets


def test_preset_links_present(demo_client):
    _, html = get_page(demo_client)
    links = preset_links(html)
    for label in ("This month", "Last 30 days", "All time"):
        assert label in links, f"Missing preset '{label}'"


def test_this_month_preset_range(demo_client):
    _, html = get_page(demo_client)
    href = preset_links(html)["This month"][0]
    assert f"start={MONTH_START.isoformat()}" in href


def test_last_30_days_preset_range(demo_client):
    _, html = get_page(demo_client)
    href = preset_links(html)["Last 30 days"][0]
    expected_starts = {
        (TODAY - timedelta(days=29)).isoformat(),
        (TODAY - timedelta(days=30)).isoformat(),
    }
    assert any(f"start={s}" in href for s in expected_starts), href
    assert f"end={TODAY.isoformat()}" in href


def test_all_time_preset_goes_to_plain_profile(demo_client):
    _, html = get_page(demo_client)
    href = preset_links(html)["All time"][0]
    assert href.rstrip("?") == "/profile"


def test_all_time_active_when_unfiltered(demo_client):
    _, html = get_page(demo_client)
    links = preset_links(html)
    assert "active" in links["All time"][1]
    assert "active" not in links["This month"][1]
    assert "active" not in links["Last 30 days"][1]


@pytest.mark.parametrize("label", ["This month", "Last 30 days"])
def test_following_preset_marks_it_active_and_returns_200(demo_client, label):
    _, html = get_page(demo_client)
    href = preset_links(html)[label][0]
    resp = demo_client.get(href)
    assert resp.status_code == 200
    page = resp.data.decode("utf-8")
    links = preset_links(page)
    assert "active" in links[label][1], f"'{label}' should be active"
    others = [k for k in links if k != label]
    for other in others:
        assert "active" not in links[other][1], f"'{other}' should not be active"
    assert ERROR_MARK not in page


def test_this_month_preset_includes_seeded_current_month_expenses(demo_client):
    _, html = get_page(demo_client)
    href = preset_links(html)["This month"][0]
    page = demo_client.get(href).data.decode("utf-8")
    # Seed has expenses on days 1-8 of this month; day 1 is always <= today.
    assert "No expenses in this period." not in page
    assert "₹0.00" not in page


def test_custom_range_has_no_active_preset(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-31")
    for label, (_, attrs) in preset_links(html).items():
        assert "active" not in attrs, f"'{label}' must not be active for custom range"


# ---------------------------------------------------------- user isolation


def test_other_user_never_sees_demo_expenses(user_client):
    start = MONTH_START.isoformat()
    for params in ({}, {"start": start}, {"end": "2999-12-31"},
                   {"start": "1999-01-01", "end": "2999-12-31"}):
        _, html = get_page(user_client, **params)
        assert "Lunch with friends" not in html, f"Leak with {params}"
        assert "Demo User" not in html


def test_demo_never_sees_other_users_expenses(client, user):
    login(client, **DEMO)
    _, html = get_page(client, start="2026-03-01", end="2026-03-31")
    for desc in ("edge-start", "middle", "edge-end"):
        assert desc not in html, f"Demo user must not see {desc}"


# ---------------------------------------- query helpers: direct unit tests


def test_summary_stats_range_is_inclusive(app, user):
    stats = queries.get_summary_stats(user, start="2026-03-01", end="2026-03-31")
    assert stats["transaction_count"] == 3
    assert stats["total_spent"] == pytest.approx(350.75)
    assert stats["top_category"] == "Transport"


def test_summary_stats_start_only(app, user):
    stats = queries.get_summary_stats(user, start="2026-03-31")
    assert stats["transaction_count"] == 2
    assert stats["total_spent"] == pytest.approx(50.25 + 777.00)


def test_summary_stats_end_only(app, user):
    stats = queries.get_summary_stats(user, end="2026-03-01")
    assert stats["transaction_count"] == 2
    assert stats["total_spent"] == pytest.approx(100.00 + 999.00)


def test_summary_stats_empty_range_returns_zeros(app, user):
    stats = queries.get_summary_stats(user, start="2000-01-01", end="2000-01-02")
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


def test_transactions_range_inclusive_and_newest_first(app, user):
    rows = queries.get_recent_transactions(user, start="2026-03-01", end="2026-03-31")
    assert [r["description"] for r in rows] == ["edge-end", "middle", "edge-start"]


def test_transactions_empty_range_returns_empty_list(app, user):
    assert queries.get_recent_transactions(user, start="2000-01-01", end="2000-01-02") == []


def test_transactions_limit_applies_within_range(app):
    uid = make_user()
    for day in range(1, 29):
        add_expense(uid, 1, "Food", f"2026-05-{day:02d}", f"d{day:02d}")
    add_expense(uid, 1, "Food", "2026-06-01", "outside")
    rows = queries.get_recent_transactions(uid, start="2026-05-01", end="2026-05-28")
    assert len(rows) == 10, "Default limit of 10 must hold inside a range"
    assert rows[0]["description"] == "d28"
    assert all(r["description"] != "outside" for r in rows)
    rows3 = queries.get_recent_transactions(uid, limit=3, start="2026-05-01", end="2026-05-28")
    assert len(rows3) == 3


def test_breakdown_range_scoped_and_sums_to_100(app, user):
    rows = queries.get_category_breakdown(user, start="2026-03-01", end="2026-03-31")
    assert {r["name"] for r in rows} == {"Food", "Transport"}
    assert sum(r["pct"] for r in rows) == 100


def test_breakdown_empty_range_returns_empty_list(app, user):
    assert queries.get_category_breakdown(user, start="2000-01-01", end="2000-01-02") == []


def test_helpers_range_is_scoped_per_user(app, user):
    stats = queries.get_summary_stats(demo_id(), start="2026-03-01", end="2026-03-31")
    assert stats["transaction_count"] == 0


def test_helpers_treat_injection_string_as_data_not_sql(app, user):
    # Helpers receive already-validated dates in practice; a hostile string
    # must still never be executed as SQL.
    evil = "' OR 1=1 --"
    rows = queries.get_recent_transactions(user, start=evil)
    assert isinstance(rows, list)
    assert fetch_all("SELECT COUNT(*) AS n FROM expenses")[0]["n"] >= 5


# --------------------------------- backward-compatible helper signatures


@pytest.mark.parametrize(
    "func",
    [
        queries.get_summary_stats,
        queries.get_recent_transactions,
        queries.get_category_breakdown,
    ],
)
def test_helpers_accept_optional_start_end_defaulting_to_none(func):
    params = inspect.signature(func).parameters
    assert "start" in params and "end" in params
    assert params["start"].default is None
    assert params["end"].default is None


def test_recent_transactions_keeps_limit_default_of_10():
    assert inspect.signature(queries.get_recent_transactions).parameters["limit"].default == 10


def test_helpers_still_callable_with_only_user_id(app):
    uid = demo_id()
    assert queries.get_summary_stats(uid)["transaction_count"] == 8
    assert len(queries.get_recent_transactions(uid)) == 8
    assert len(queries.get_category_breakdown(uid)) == 7


def test_helpers_none_equals_unfiltered(app):
    uid = demo_id()
    assert queries.get_summary_stats(uid, start=None, end=None) == queries.get_summary_stats(uid)
    assert queries.get_category_breakdown(uid, start=None, end=None) == queries.get_category_breakdown(uid)


# --------------------------------------------- consistency / hygiene


def test_page_numbers_agree_across_sections(user_client):
    _, html = get_page(user_client, start="2026-03-01", end="2026-03-10")
    # Only edge-start (100.00) and middle (200.50) are in range.
    assert "₹300.50" in html
    assert "edge-end" not in html
    assert html.count("profile-breakdown-item") == 2


@pytest.mark.parametrize(
    "params",
    [{}, {"start": "2026-03-01", "end": "2026-03-31"}, {"start": "garbage"}, {"start": "2026-03-31", "end": "2026-03-01"}],
)
def test_no_dollar_pound_or_inline_style_in_rendered_page(user_client, params):
    _, html = get_page(user_client, **params)
    assert "$" not in html, "Currency must stay rupee"
    assert "£" not in html
    assert "style=" not in html, "No inline styles allowed"


def test_template_has_no_inline_style_or_hardcoded_urls():
    path = os.path.join(ROOT, "templates", "profile.html")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert "style=" not in src
    assert "<style" not in src
    assert 'href="/' not in src
    assert 'action="/' not in src


def test_one_invalid_date_is_dropped_but_valid_one_still_applies(client, user):
    """Pins the documented behaviour: error shown, the valid bound still filters."""
    login(client, **OTHER)
    resp, html = get_page(client, start="garbage", end="2026-03-10")
    assert resp.status_code == 200
    assert "profile-filter-error" in html
    assert "middle" in html and "edge-start" in html
    assert "after-range" not in html
