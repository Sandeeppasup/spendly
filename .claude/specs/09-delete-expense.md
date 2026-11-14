# Spec: Delete Expense

## Overview
Step 9 lets a signed-in user permanently remove an expense they recorded. The
`/expenses/<id>/delete` route is currently a raw-string stub. This step turns it
into a two-stage flow: a GET renders a confirmation page showing the expense's
details, and only a POST actually deletes the row and redirects back to the
profile. Deleting must never happen on GET (links, prefetchers and cross-site
requests can trigger GETs), so the profile's per-row "Delete" link leads to the
confirmation page. Only the owner may delete; any other id (missing or owned by
another user) returns 404. This completes the add / edit / delete CRUD set for
expenses.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 3: Login / Logout (`g.current_user`, session)
- Step 5: Profile backend routes (`database/queries.py`, `get_recent_transactions()` returns `id`)
- Step 6: Date filter (redirect after delete returns to the profile page)
- Step 7: Add expense (`expense_form.css`, form layout)
- Step 8: Edit expense (`get_expense()`, Edit link / actions column in `profile.html`)

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page showing the
  expense's amount, category, date and description with "Delete" and "Cancel"
  controls — logged-in (signed-out visitors redirect to `/login`; unknown id or
  an expense owned by another user → `abort(404)`). GET never modifies data.
- `POST /expenses/<int:id>/delete` — delete the expense, redirect to `/profile`
  — logged-in (signed-out → redirect to `/login`, nothing deleted). Same 404 rule
  for missing / foreign expenses.

The existing `delete_expense` endpoint name is kept so `url_for('delete_expense',
id=...)` works. The route's `methods` change from the default GET to
`["GET", "POST"]`.

## Database changes
No schema changes (verified against `database/db.py`).

New helper in `database/db.py`:
- `delete_expense(expense_id, user_id)` — parameterised
  `DELETE FROM expenses WHERE id = ? AND user_id = ?`, commits, returns `True`
  if a row was deleted and `False` otherwise. Closes the connection with
  `try/finally`.

`get_expense()` (already exists) is reused to load the expense for the
confirmation page.

## Templates
- **Create:** `templates/delete_expense.html` — extends `base.html`; heading
  "Delete expense", a short warning that this cannot be undone, a read-only
  summary of the expense (₹ amount via the `inr` filter, category, date,
  description), a `<form method="POST" action="{{ url_for('delete_expense',
  id=expense_id) }}">` with a "Delete" submit button, and a Cancel link to
  `url_for('profile')`.
- **Modify:** `templates/profile.html` — add a "Delete" link next to the existing
  "Edit" link in each transaction row, using `url_for('delete_expense', id=t.id)`
  (inside the existing `col-actions` cell; widen it if needed).

## Files to change
- `app.py` — implement `delete_expense` (GET confirm + POST delete), import
  `delete_expense` helper from `database.db` under a non-clashing name (e.g.
  `delete_expense as remove_expense`, or name the db helper `remove_expense`)
- `database/db.py` — add the delete helper
- `templates/profile.html` — Delete link
- `static/css/profile.css` — style for the Delete link (danger colour via CSS variable)
- `static/css/expense_form.css` — styles for the confirmation summary and the
  danger button, only if reuse of existing classes is not enough
- `CLAUDE.md` — mark `/expenses/<id>/delete` implemented (Step 9), document the
  new `db.py` helper, `delete_expense.html` and `tests/test_delete_expense.py`

## Files to create
- `templates/delete_expense.html`
- `tests/test_delete_expense.py` — route and helper tests
- `.claude/specs/09-delete-expense.md` — this spec

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only; never format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Deletion happens on POST only; GET must never delete
- DB logic stays in `database/db.py`; the route fetches, calls the helper and
  redirects (always close connections with `try/finally`)
- Ownership is enforced in SQL (`AND user_id = ?`) using
  `g.current_user["id"]`; never trust a `user_id` field from the form
- Use `abort(404)` for missing or foreign expenses, never a bare error string;
  foreign and missing ids must be indistinguishable
- The DB helper name must not shadow the route function `delete_expense` in `app.py`
- Use `url_for()` for every link and redirect
- No inline styles and no inline `<style>` tags
- Vanilla JS only, and none is required: the flow must work with JS disabled
- Currency stays ₹
- Do not change `add_expense` or `edit_expense` behaviour

## Definition of done
- [ ] Signed out, visiting `/expenses/<id>/delete` redirects to `/login`; a signed-out POST deletes nothing
- [ ] Each row in the profile transaction list has a Delete link that opens that expense's confirmation page
- [ ] The confirmation page shows the expense's amount, category, date and description
- [ ] Visiting the confirmation page (GET) does not delete the expense
- [ ] Cancel returns to `/profile` and the expense is still listed
- [ ] Confirming (POST) redirects to `/profile` and the expense no longer appears in the transaction list
- [ ] Total spent, transaction count and the category breakdown on `/profile` reflect the deletion
- [ ] Only the targeted expense is removed; other expenses are untouched
- [ ] A non-existent expense id returns 404 on both GET and POST
- [ ] GET or POST on another user's expense id returns 404 and leaves that expense in the database
- [ ] A second POST for an already-deleted id returns 404
- [ ] A submitted `user_id` field in the POST body is ignored
- [ ] `/expenses/add` and `/expenses/<id>/edit` still work
- [ ] `pytest` passes, including the new `tests/test_delete_expense.py`
