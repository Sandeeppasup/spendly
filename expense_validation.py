"""Add-expense form validation. Pure helpers: no Flask, no database access."""
import math
from datetime import datetime

from database.db import CATEGORIES

MAX_AMOUNT = 10_000_000
MAX_DESCRIPTION = 200


def validate_expense_form(form):
    """Validate an add-expense form (any mapping with .get).

    Returns (cleaned, error). On success cleaned is a dict with amount,
    category, expense_date and description and error is None; on failure cleaned is
    None and error is a user-facing message. Never reads a user id.
    """
    raw_amount = (form.get("amount") or "").strip()
    if not raw_amount:
        return None, "Amount is required."
    try:
        amount = float(raw_amount)
    except ValueError:
        return None, "Enter a valid amount."
    if not math.isfinite(amount):
        return None, "Enter a valid amount."
    amount = round(amount, 2)
    if amount <= 0:
        return None, "Amount must be greater than 0."
    if amount > MAX_AMOUNT:
        return None, f"Amount cannot exceed {MAX_AMOUNT:,}."

    category = (form.get("category") or "").strip()
    if category not in CATEGORIES:
        return None, "Choose a category from the list."

    raw_date = (form.get("date") or "").strip()
    try:
        expense_date = datetime.strptime(raw_date, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None, "Enter a valid date."

    description = (form.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION:
        return None, f"Description must be {MAX_DESCRIPTION} characters or fewer."
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in description):
        return None, "Description contains invalid characters."

    return {
        "amount": amount,
        "category": category,
        "expense_date": expense_date,
        "description": description,
    }, None
