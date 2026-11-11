# Spec: Add Expense

## Overview
Step 7 lets a signed-in user record a new expense. Until now the only expenses
in the app are the seeded demo rows; the `/expenses/add` route is a raw-string
stub. This step turns it into a real form page (amount, category, date,
description) that validates input, inserts a row for the current user and
redirects back to the profile page, where the new expense shows up in the
summary, transaction list and category breakdown. It is the first write path
for expenses and sets the pattern the edit (Step 8) and delete (Step 9) steps
will follow.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES`)
- Step 3: Login / Logout (`g.current_user`, session)
- Step 4: Profile page static UI (`profile.html`, `profile.css`)
- Step 5: Profile backend routes (profile reads from `database/queries.py`)
- Step 6: Date filter (new expenses must respect the filter when shown)

## Routes
- `GET /expenses/add` — render the empty add-expense form; date pre-filled
  with today — logged-in (signed-out visitors redirect to `/login`)
- `POST /expenses/add` — validate the form, insert the expense for the
  current user, redirect to `/profile` — logged-in
  - On validation failure re-render the form with an inline `error` and the
    submitted values preserved (HTTP 200, no insert)

The existing `add_expense` endpoint name is kept so `url_for('add_expense')`
works everywhere. No other new routes.

## Database changes
No schema changes. The `expenses` table already has `amount REAL`,
`category TEXT`, `date TEXT` (ISO), `description TEXT` and
`user_id → users.id` (verified against `database/db.py`).

New helper in `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — inserts via
  a parameterised query, commits, returns the new row id. Does not validate;
  callers must pass already-validated values.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; a POST form
  with: amount (`type="number"`, `step="0.01"`, `min="0.01"`), category
  (`<select>` built from `CATEGORIES`), date (`type="date"`, default today),
  description (optional text). Shows the inline error, keeps submitted values
  on failure, has a Cancel link back to `url_for('profile')`.
- **Modify:** `templates/profile.html` — add an "Add expense" link/button
  using `url_for('add_expense')`, plus the empty-state text pointing to it.

## Files to change
- `app.py` — make `add_expense` accept GET and POST, redirect when signed out,
  validate and call `create_expense()`
- `database/db.py` — add `create_expense()`
- `templates/profile.html` — "Add expense" link
- `static/css/profile.css` — styling for the new link if needed
- `CLAUDE.md` — mark `/expenses/add` implemented (Step 7); add
  `create_expense()` to the `db.py` description and the new tests file

## Files to create
- `templates/add_expense.html`
- `static/css/expense_form.css` — form-page-only styles (linked from the
  template via a `head` block, as other page-specific CSS is)
- `tests/test_add_expense.py` — route and helper tests
- `.claude/specs/07-add-expense.md` — this spec

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only; never format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline `<style>` tags
- DB logic stays in `database/db.py`; the route only validates, calls the
  helper and redirects (always close connections with `try/finally`)
- Always insert with `g.current_user["id"]`; never trust a `user_id` from the
  form
- Server-side validation (do not rely on HTML attributes):
  - amount: parseable as a number, finite (reject `nan`/`inf`), greater than 0
    and a sensible upper bound; stored as `float` rounded to 2 decimals
  - category: must be one of `CATEGORIES`
  - date: valid ISO `YYYY-MM-DD` via `datetime.strptime`; reject impossible
    dates (e.g. `2026-02-31`)
  - description: optional, stripped, max 200 characters; empty stored as
    `NULL`/empty consistently with seed data
- Use `abort()` for HTTP errors, never bare error strings
- Use `url_for()` for every link and redirect
- Vanilla JS only, and none is required: the form must work with JS disabled
- Currency stays ₹
- Do not implement the edit or delete stub routes

## Definition of done
- [ ] Signed out, visiting `/expenses/add` redirects to `/login`; a signed-out POST inserts nothing
- [ ] Signed in, `/expenses/add` shows a form with amount, category (all 7 categories), date defaulting to today, and optional description
- [ ] Submitting a valid expense redirects to `/profile` and the expense appears in the transaction list
- [ ] Total spent, transaction count and the category breakdown on `/profile` update to include the new expense
- [ ] The new expense belongs to the signed-in user and is not visible to any other user
- [ ] Empty, zero, negative, non-numeric, `nan` and `inf` amounts show an inline error and insert nothing
- [ ] A category not in `CATEGORIES` (e.g. tampered POST) shows an inline error and inserts nothing
- [ ] An invalid or impossible date shows an inline error and inserts nothing
- [ ] A description over 200 characters shows an inline error
- [ ] After a failed submit the form keeps the entered values
- [ ] A submitted `user_id` field in the POST body is ignored
- [ ] A SQL-injection string in description is stored verbatim and does not break the database
- [ ] The profile page has an "Add expense" link that uses `url_for`
- [ ] Cancel returns to `/profile` without saving
- [ ] `/expenses/<id>/edit` and `/expenses/<id>/delete` are still stubs
- [ ] `pytest` passes, including the new `tests/test_add_expense.py`
