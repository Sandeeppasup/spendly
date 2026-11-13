# Spec: Edit Expense

## Overview
Step 8 lets a signed-in user correct an expense they previously recorded. The
`/expenses/<id>/edit` route is currently a raw-string stub. This step turns it
into a real form page pre-filled with the expense's current values, validates
changes with the same rules as the add form, updates the row and redirects back
to the profile page. Only the owner of an expense may edit it; any other id
(missing or belonging to another user) returns 404. It reuses the validation
and form layout from Step 7 and gives the profile transaction list the
per-row "Edit" link that Step 9 (delete) will sit beside.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES`)
- Step 3: Login / Logout (`g.current_user`, session)
- Step 5: Profile backend routes (`database/queries.py`)
- Step 6: Date filter (redirect after edit returns to the profile page)
- Step 7: Add expense (`validate_expense_form()`, `expense_form.css`, form layout)

## Routes
- `GET /expenses/<int:id>/edit` — render the form pre-filled with the
  expense's current amount, category, date and description — logged-in
  (signed-out visitors redirect to `/login`; unknown id or an expense owned by
  another user → `abort(404)`)
- `POST /expenses/<int:id>/edit` — validate via `validate_expense_form()`,
  update the expense, redirect to `/profile` — logged-in
  - On validation failure re-render the form with an inline `error` and the
    submitted values preserved (HTTP 200, no update)
  - Same 404 rule for missing / foreign expenses, checked before validation

The existing `edit_expense` endpoint name is kept so `url_for('edit_expense',
id=...)` works. The delete stub is not touched.

## Database changes
No schema changes. The `expenses` table already has everything needed
(verified against `database/db.py`).

New helpers in `database/db.py`:
- `get_expense(expense_id, user_id)` — returns the `Row` for that expense only
  if it belongs to `user_id`, else `None` (`WHERE id = ? AND user_id = ?`)
- `update_expense(expense_id, user_id, amount, category, expense_date, description)`
  — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`, commits, returns
  `True` if a row was changed and `False` otherwise. Does not validate; callers
  pass already-validated values. `user_id` and `created_at` are never changed.

Change in `database/queries.py`:
- `get_recent_transactions()` also returns each row's `id` (add `id` to the
  SELECT and the result dict) so the profile can link to the edit page.

## Templates
- **Create:** `templates/edit_expense.html` — extends `base.html`; same fields
  and layout as `add_expense.html` (amount, category select from `CATEGORIES`,
  date, description), posting to `url_for('edit_expense', id=expense_id)`,
  heading "Edit expense", submit button "Save changes", Cancel link to
  `url_for('profile')`, inline error, submitted values kept on failure.
- **Modify:** `templates/profile.html` — add an "Edit" link per transaction
  row using `url_for('edit_expense', id=t.id)` (new narrow actions column; update
  the empty-state `colspan`).

## Files to change
- `app.py` — implement `edit_expense` (GET + POST), import `get_expense` and
  `update_expense`
- `database/db.py` — add `get_expense()` and `update_expense()`
- `database/queries.py` — include `id` in `get_recent_transactions()`
- `templates/profile.html` — Edit link column
- `static/css/profile.css` — style for the Edit link / actions column
- `CLAUDE.md` — mark `/expenses/<id>/edit` implemented (Step 8), document the
  new `db.py` helpers, `edit_expense.html` and `tests/test_edit_expense.py`

## Files to create
- `templates/edit_expense.html`
- `tests/test_edit_expense.py` — route and helper tests
- `.claude/specs/08-edit-expense.md` — this spec

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only; never format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline `<style>` tags; reuse `expense_form.css` for
  the edit page rather than copying it
- DB logic stays in `database/db.py`; the route fetches, validates, calls the
  helper and redirects (always close connections with `try/finally`)
- Ownership is enforced in SQL (`AND user_id = ?`) using
  `g.current_user["id"]`; never trust a `user_id` or `id` field from the form
- Reuse `validate_expense_form()` unchanged — do not duplicate validation
- Use `abort(404)` for missing or foreign expenses, never a bare error string;
  foreign and missing ids must be indistinguishable
- Use `url_for()` for every link and redirect
- Vanilla JS only, and none is required: the form must work with JS disabled
- Currency stays ₹
- Do not implement the delete stub route
- Do not change the `add_expense` route or its tests' behaviour

## Definition of done
- [ ] Signed out, visiting `/expenses/<id>/edit` redirects to `/login`; a signed-out POST changes nothing
- [ ] Each row in the profile transaction list has an Edit link that opens that expense's edit page
- [ ] The edit page is pre-filled with the expense's current amount, category, date and description
- [ ] Submitting valid changes redirects to `/profile` and the updated values appear in the transaction list
- [ ] Total spent and the category breakdown on `/profile` reflect the edited amount/category
- [ ] Editing does not create a new expense (transaction count unchanged)
- [ ] A non-existent expense id returns 404
- [ ] Visiting or POSTing to another user's expense id returns 404 and leaves that expense unchanged
- [ ] Empty, zero, negative, non-numeric, `nan` and `inf` amounts show an inline error and change nothing
- [ ] A category not in `CATEGORIES`, an invalid/impossible date, or a description over 200 characters shows an inline error and changes nothing
- [ ] After a failed submit the form keeps the entered values (not the stored ones)
- [ ] A submitted `user_id` field in the POST body is ignored; the owner does not change
- [ ] A SQL-injection string in description is stored verbatim and does not break the database
- [ ] Clearing the description saves successfully
- [ ] Cancel returns to `/profile` without saving
- [ ] `/expenses/add` still works and `/expenses/<id>/delete` is still a stub
- [ ] `pytest` passes, including the new `tests/test_edit_expense.py`
