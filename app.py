import os
import sqlite3
from datetime import date

from flask import Flask, abort, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database import queries
from date_filters import build_presets, format_range_label, parse_date_range
from expense_validation import MAX_DESCRIPTION, validate_expense_form

# NOTE: db.get_user_by_id returns a sqlite3.Row for the session loader. The
# profile card uses queries.get_user_by_id (a dict) — always call it qualified.
from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_expense,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
# Set SECRET_KEY in the environment for any real deployment. The fallback is
# for local development only and must not be relied on in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
# Reject oversized request bodies (413) before any form parsing.
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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


@app.template_filter("inr")
def format_inr(value):
    """Format a number as 1,234.50 (templates add the rupee sign)."""
    return f"{float(value):,.2f}"


def _initials(name):
    words = name.split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


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

    user_id = g.current_user["id"]
    user = queries.get_user_by_id(user_id)
    if user is None:
        return redirect(url_for("login"))
    user["initials"] = _initials(user["name"])
    start, end, date_error = parse_date_range(request.args)
    return render_template(
        "profile.html",
        user=user,
        stats=queries.get_summary_stats(user_id, start=start, end=end),
        transactions=queries.get_recent_transactions(user_id, start=start, end=end),
        categories=queries.get_category_breakdown(user_id, start=start, end=end),
        start=start,
        end=end,
        date_error=date_error,
        presets=build_presets(start, end),
        range_label=format_range_label(start, end),
    )

@app.route("/analytics")
def analytics():
    if not g.current_user:
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not g.current_user:
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        cleaned, error = validate_expense_form(request.form)
        if error is None:
            create_expense(g.current_user["id"], **cleaned)
            return redirect(url_for("profile"))

    form = request.form if request.method == "POST" else {}
    return render_template(
        "add_expense.html",
        max_description=MAX_DESCRIPTION,
        categories=CATEGORIES,
        today=date.today().isoformat(),
        form=form,
        error=error,
    )


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not g.current_user:
        return redirect(url_for("login"))

    user_id = g.current_user["id"]
    expense = get_expense(id, user_id)
    if expense is None:
        abort(404)

    error = None
    if request.method == "POST":
        cleaned, error = validate_expense_form(request.form)
        if error is None:
            if not update_expense(id, user_id, **cleaned):
                abort(404)
            return redirect(url_for("profile"))
        form = request.form
    else:
        form = {
            "amount": f"{expense['amount']:.2f}",
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        }

    return render_template(
        "edit_expense.html",
        expense_id=id,
        max_description=MAX_DESCRIPTION,
        categories=CATEGORIES,
        form=form,
        error=error,
    )


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
