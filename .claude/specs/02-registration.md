# Spec: Registration

## Overview
Make the existing `/register` page functional so a visitor can create a Spendly account. Today `GET /register` only renders a static form whose `POST` has nowhere to go. This step adds the `POST` handler: validate input, hash the password, insert a row into `users`, and send the new user on to the login page. It is the first write path in the app and the prerequisite for login (Step 3), which has no accounts to authenticate against except the seeded demo user.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`)

## Routes
- `GET /register` — render the registration form (already exists; unchanged behaviour) — public
- `POST /register` — validate the form, create the user, redirect to `/login` on success; re-render the form with an error message on failure — public

The existing `register` view function in `app.py` is extended to accept both methods. `POST /login` is **not** part of this step.

## Database changes
No database changes. The existing `users` table already has everything required (`name`, `email UNIQUE`, `password_hash`, `created_at`).

New helper functions in `database/db.py` (DB logic must not live in the route):
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row with a parameterised query, returns the new user id. Lets `sqlite3.IntegrityError` propagate when the email already exists.
- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None`. (Not needed by the registration route if the UNIQUE constraint is relied on, but required by Step 3 and cheap to add now; omit if it ends up unused.)

Both open their connection via `get_db()` and close it in a `try/finally`.

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Change `<form action="/register">` to `action="{{ url_for('register') }}"` (CLAUDE.md: never hardcode URLs)
  - Re-populate the `name` and `email` inputs from submitted values after a validation error (never re-populate the password)

## Files to change
- `app.py` — extend the `register` route to handle `POST`; import `create_user` and the Flask helpers it needs (`request`, `redirect`, `url_for`)
- `database/db.py` — add `create_user()` (and `get_user_by_email()` if used)
- `templates/register.html` — see above

## Files to create
- `tests/test_registration.py` — pytest-flask tests covering the Definition of done (use a temporary database, not `expense_tracker.db`)

## New dependencies
No new dependencies. (`pytest` and `pytest-flask` are already in `requirements.txt`.)

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no f-strings or `%` formatting in SQL
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py`; the route only validates, calls the helper, and redirects/renders
- Server-side validation (the HTML `required` attribute is not enough):
  - `name`: required, non-empty after stripping whitespace
  - `email`: required, stripped and lower-cased before storing, must contain `@` with text on both sides
  - `password`: required, minimum 8 characters (matches the placeholder text already in the template)
- Duplicate email: catch `sqlite3.IntegrityError` from the UNIQUE constraint (don't pre-check with a SELECT, which races) and show "An account with that email already exists."
- On any validation failure return the form with HTTP 200 and the `error` variable the template already supports; do not use bare string returns
- On success redirect (`302`) to `url_for('login')` — Post/Redirect/Get, so a refresh doesn't resubmit
- Do not log the user in or create a session — that belongs to Step 3
- Do not implement any other stub route (`/logout`, `/profile`, `/expenses/*`)
- Keep the app on port 5001

## Definition of done
- [ ] `GET /register` still renders the form with status 200
- [ ] Submitting valid name, email and an 8+ character password creates a row in `users` and redirects to `/login`
- [ ] The stored `password_hash` is a werkzeug hash (not the plain password) and `check_password_hash` accepts the original password
- [ ] The stored email is lower-cased and trimmed (registering `  Foo@Example.COM ` stores `foo@example.com`)
- [ ] Registering the same email again (in any letter case) re-renders the form with "An account with that email already exists." and creates no second row
- [ ] Empty/whitespace-only name, malformed email, or a password shorter than 8 characters re-renders the form with a clear error and creates no row
- [ ] After a failed submission the name and email fields keep their values; the password field is empty
- [ ] No form `action` or link in `register.html` is a hardcoded URL
- [ ] Every query added uses `?` placeholders
- [ ] The demo user (`demo@spendly.com`) is unaffected and `seed_db()` still does not duplicate data on restart
- [ ] `pytest tests/test_registration.py` passes
- [ ] `python app.py` starts without errors on port 5001
