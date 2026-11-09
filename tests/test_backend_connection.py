import re

import database.db as dbmod
from app import format_inr
from conftest import fetch_all
from database import queries

DEMO = {"email": "demo@spendly.com", "password": "demo123"}


def demo_id():
    return fetch_all("SELECT id FROM users WHERE email = 'demo@spendly.com'")[0]["id"]


def make_user(email="new@example.com"):
    return dbmod.create_user("New Person", email, "password123")


def add_expense(user_id, amount, category, date, description="x"):
    conn = dbmod.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------- get_user_by_id


def test_user_dict_for_demo(app):
    user = queries.get_user_by_id(demo_id())
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert re.fullmatch(r"[A-Z][a-z]+ \d{4}", user["member_since"])


def test_member_since_from_created_at(app):
    uid = demo_id()
    conn = dbmod.get_db()
    try:
        conn.execute(
            "UPDATE users SET created_at = '2026-01-15 10:00:00' WHERE id = ?", (uid,)
        )
        conn.commit()
    finally:
        conn.close()
    assert queries.get_user_by_id(uid)["member_since"] == "January 2026"


def test_unknown_user_is_none(app):
    assert queries.get_user_by_id(99999) is None


# ------------------------------------------------------- get_summary_stats


def test_summary_for_demo(app):
    stats = queries.get_summary_stats(demo_id())
    assert stats["total_spent"] == 6939.25
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Shopping"


def test_summary_without_expenses(app):
    assert queries.get_summary_stats(make_user()) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_summary_tie_is_alphabetical(app):
    uid = make_user()
    add_expense(uid, 50, "Food", "2026-01-01")
    add_expense(uid, 50, "Bills", "2026-01-02")
    assert queries.get_summary_stats(uid)["top_category"] == "Bills"


# ------------------------------------------------- get_recent_transactions


def test_transactions_newest_first(app):
    rows = queries.get_recent_transactions(demo_id())
    assert len(rows) == 8
    assert rows[0]["description"] == "Lunch with friends"
    assert rows[-1]["description"] == "Groceries"
    isos = [r["iso"] for r in rows]
    assert isos == sorted(isos, reverse=True)
    for key in ("iso", "date", "description", "category", "amount"):
        assert key in rows[0]


def test_transactions_empty(app):
    assert queries.get_recent_transactions(make_user()) == []


def test_transactions_limit(app):
    uid = make_user()
    for day in range(1, 13):
        add_expense(uid, 10, "Food", f"2026-01-{day:02d}")
    assert len(queries.get_recent_transactions(uid)) == 10
    assert len(queries.get_recent_transactions(uid, limit=3)) == 3


def test_transactions_same_date_newest_id_first(app):
    uid = make_user()
    add_expense(uid, 1, "Food", "2026-01-05", "first")
    add_expense(uid, 2, "Food", "2026-01-05", "second")
    assert queries.get_recent_transactions(uid)[0]["description"] == "second"


def test_transaction_null_description_is_blank(app):
    uid = make_user()
    add_expense(uid, 5, "Food", "2026-01-05", None)
    assert queries.get_recent_transactions(uid)[0]["description"] == ""


# -------------------------------------------------- get_category_breakdown


def test_breakdown_for_demo(app):
    rows = queries.get_category_breakdown(demo_id())
    assert len(rows) == 7
    amounts = [r["amount"] for r in rows]
    assert amounts == sorted(amounts, reverse=True)
    assert all(isinstance(r["pct"], int) for r in rows)
    assert sum(r["pct"] for r in rows) == 100
    assert rows[0]["name"] == "Shopping" and rows[0]["pct"] == 36


def test_breakdown_remainder_goes_to_largest(app):
    uid = make_user()
    for cat in ("Bills", "Food", "Health"):
        add_expense(uid, 100, cat, "2026-01-01")
    assert [r["pct"] for r in queries.get_category_breakdown(uid)] == [34, 33, 33]


def test_breakdown_empty(app):
    assert queries.get_category_breakdown(make_user()) == []


# ---------------------------------------------------------------- isolation


def test_queries_are_scoped_per_user(app):
    uid = make_user()
    add_expense(uid, 77, "Other", "2026-01-01", "mine")
    assert [r["description"] for r in queries.get_recent_transactions(uid)] == ["mine"]
    assert queries.get_summary_stats(uid)["total_spent"] == 77
    assert queries.get_summary_stats(demo_id())["total_spent"] == 6939.25


# ------------------------------------------------------------- inr filter


def test_inr_filter():
    assert format_inr(1800) == "1,800.00"
    assert format_inr(0) == "0.00"
