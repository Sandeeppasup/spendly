"""Read-only query helpers for the profile page. No Flask imports."""
from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Return {name, email, member_since} for the profile card, or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    member_since = datetime.strptime(
        row["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")
    return {"name": row["name"], "email": row["email"], "member_since": member_since}


def _date_clause(start, end):
    """Return (sql_fragment, params) for an optional inclusive date range.

    The fragment is built from fixed strings only; dates are bound as `?`
    parameters. Callers must pass normalised 'YYYY-MM-DD' strings or None.
    """
    sql = ""
    params = []
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    return sql, tuple(params)


# ==== BEGIN transactions (subagent 1) ====
def get_recent_transactions(user_id, limit=10, *, start=None, end=None):
    clause, params = _date_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "iso": row["date"],
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]
# ==== END transactions ====


# ==== BEGIN summary (subagent 2) ====
def get_summary_stats(user_id, *, start=None, end=None):
    clause, params = _date_clause(start, end)
    conn = get_db()
    try:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses "
            "WHERE user_id = ?" + clause,
            (user_id, *params),
        ).fetchone()
        top_row = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + clause
            + " GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id, *params),
        ).fetchone()
    finally:
        conn.close()
    return {
        "total_spent": round(total, 2),
        "transaction_count": count,
        "top_category": top_row[0] if top_row else "—",
    }
# ==== END summary ====


# ==== BEGIN breakdown (subagent 3) ====
def get_category_breakdown(user_id, *, start=None, end=None):
    clause, params = _date_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " GROUP BY category "
            "ORDER BY total DESC, category ASC",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(row["total"] for row in rows)
    if not rows or grand_total == 0:
        return []

    items = [
        {
            "name": row["category"],
            "amount": round(row["total"], 2),
            "pct": int(round(row["total"] / grand_total * 100)),
        }
        for row in rows
    ]
    items[0]["pct"] += 100 - sum(item["pct"] for item in items)
    return items
# ==== END breakdown ====
