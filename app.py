import os
import sqlite3

from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
# Set SECRET_KEY in the environment for any real deployment. The fallback is
# for local development only and must not be relied on in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

with app.app_context():
    init_db()
    seed_db()


@app.before_request
def load_current_user():
    user_id = session.get("user_id")
    g.current_user = get_user_by_id(user_id) if user_id is not None else None


@app.context_processor
def inject_current_user():
    return {"current_user": g.get("current_user")}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.current_user:
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    local, sep, domain = email.partition("@")
    error = None
    if not name:
        error = "Name is required."
    elif not (sep and local and domain):
        error = "Enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."

    if error is None:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "An account with that email already exists."

    if error:
        return render_template("register.html", error=error, name=name, email=email)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user:
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email and password else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    if not g.current_user:
        return redirect(url_for("login"))

    # Hardcoded placeholder data — real queries arrive in Step 5.
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "January 2026",
    }
    stats = {
        "total_spent": "6,939.25",
        "transaction_count": 8,
        "top_category": "Shopping",
    }
    transactions = [
        {"iso": "2026-11-08", "date": "08 Nov 2026", "description": "Lunch with friends", "category": "Food", "amount": "320.75"},
        {"iso": "2026-11-07", "date": "07 Nov 2026", "description": "Miscellaneous", "category": "Other", "amount": "200.00"},
        {"iso": "2026-11-06", "date": "06 Nov 2026", "description": "New shoes", "category": "Shopping", "amount": "2,499.00"},
        {"iso": "2026-11-05", "date": "05 Nov 2026", "description": "Movie and dinner", "category": "Entertainment", "amount": "899.00"},
        {"iso": "2026-11-04", "date": "04 Nov 2026", "description": "Pharmacy", "category": "Health", "amount": "650.00"},
        {"iso": "2026-11-03", "date": "03 Nov 2026", "description": "Electricity bill", "category": "Bills", "amount": "1,800.00"},
        {"iso": "2026-11-02", "date": "02 Nov 2026", "description": "Metro card recharge", "category": "Transport", "amount": "120.50"},
        {"iso": "2026-11-01", "date": "01 Nov 2026", "description": "Groceries", "category": "Food", "amount": "450.00"},
    ]
    categories = [
        {"name": "Shopping", "amount": "2,499.00", "pct": 36},
        {"name": "Bills", "amount": "1,800.00", "pct": 26},
        {"name": "Entertainment", "amount": "899.00", "pct": 13},
        {"name": "Food", "amount": "770.75", "pct": 11},
        {"name": "Health", "amount": "650.00", "pct": 9},
        {"name": "Other", "amount": "200.00", "pct": 3},
        {"name": "Transport", "amount": "120.50", "pct": 2},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
