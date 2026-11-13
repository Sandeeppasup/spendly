# CLAUDE.md

## Project overview

Spendly is a lightweight personal expense tracker built with Flask and SQLite.

---

## Architecture
```
spendly/
├── app.py              # All routes — single file, no blueprints
├── expense_tracker.db  # SQLite file (gitignored), created by init_db()
├── date_filters.py     # Profile date-filter helpers: parse_date_range(), format_range_label(), build_presets()
├── expense_validation.py # Add-expense form validation (pure, no Flask/SQLite): validate_expense_form(form) -> (cleaned, error)
├── database/
│   ├── db.py           # SQLite helpers: get_db(), init_db(), seed_db(), create_user(), create_expense() and update_expense() (no validation — callers pass validated values), get_expense(expense_id, user_id) (owner-only Row or None), DB_PATH, CATEGORIES
│   └── queries.py      # Profile-page read helpers (no Flask): get_user_by_id() (dict, not the db.py Row version), get_summary_stats(), get_recent_transactions() (rows include `id`), get_category_breakdown() — the last three take optional keyword-only `start`/`end` ISO dates (inclusive) via the private `_date_clause()`
├── templates/
│   ├── base.html       # Shared layout — all templates must extend this
│   └── *.html          # One template per page (landing, login, register, terms, privacy)
├── static/
│   ├── css/
│   │   ├── style.css       # Global styles
│   │   ├── landing.css     # Landing-page-only styles
│   │   ├── profile.css     # Profile-page-only styles
│   │   └── expense_form.css # Add-expense-page-only styles
│   └── js/
│       └── main.js         # Vanilla JS only
├── .claude/
│   ├── commands/       # Project slash commands: /create-spec, /seed-user, /seed-expense
│   └── specs/          # Feature specs: 01-database-setup.md, 02-registration.md
├── tests/
│   ├── conftest.py     # Redirects DB_PATH to a temp file; provides the `app` fixture
│   ├── test_registration.py
│   ├── test_login.py
│   ├── test_profile.py
│   ├── test_profile_date_filter.py
│   ├── test_add_expense.py
│   ├── test_edit_expense.py
│   └── test_backend_connection.py
└── requirements.txt
```

**Database schema** (`database/db.py`):
- `users(id, name, email UNIQUE, password_hash, created_at)`
- `expenses(id, user_id → users.id, amount REAL, category, date TEXT ISO, description, created_at)`
- `CATEGORIES`: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `seed_db()` is a no-op once any user exists; otherwise inserts demo user `demo@spendly.com` / `demo123` with sample expenses
- Passwords use `werkzeug.security.generate_password_hash`
- `create_user(name, email, password)` hashes the password, inserts, and returns the new id. It does **not** normalise or catch errors: callers must pass a stripped, lower-cased email (the UNIQUE constraint is case-sensitive) and handle `sqlite3.IntegrityError` for duplicates

**Where things belong:**
- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` only, never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file, not inline `<style>` tags

---

## Code style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always use parameterized queries (`?` placeholders) — never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`

---

## Tech constraints

- **Flask only** — no FastAPI, no Django, no other web frameworks
- **SQLite only** — no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** — no React, no jQuery, no npm packages
- **No new pip packages** — work within `requirements.txt` as-is unless explicitly told otherwise
- Python 3.10+ assumed — f-strings and `match` statements are fine

---

## Subagent Policy
- Always use a builtin explore subagent for codebase exploration 
  before implementing any new feature
- Never auto-launch the custom subagents in `.claude/agents/`
  (test-writer, test-runner, quality-reviewer, security-reviewer).
  The user runs them manually after implementation via
  `/test-feature <spec>` and `/code-review-feature <spec>`.
  After implementing, stop and report instead
- When asked to plan, delegate codebase research 
  to a subagent before presenting the plan
- always use a builtin plan subagent in plan mode

---

## Commands
```bash
# Setup
python -m venv venv               # Windows here: use `py -m venv venv` (python/python3 are Store placeholders)
source venv/bin/activate          # Windows: venv\Scripts\activate (Git Bash: source venv/Scripts/activate)
pip install -r requirements.txt

# Run dev server (port 5001)
python app.py

# Run all tests (use venv\Scripts\python.exe -m pytest if pytest isn't on PATH)
pytest

# Run a specific test file
pytest tests/test_registration.py

# Run a specific test by name
pytest -k "test_name"

# Run tests with output visible
pytest -s
```

---

## Implemented vs stub routes

| Route | Status |
|---|---|
| `GET /` | Implemented — renders `landing.html` |
| `GET /register` | Implemented — renders `register.html` |
| `POST /register` | Implemented (Step 2) — validates, calls `create_user()`, redirects to `/login`; re-renders with `error`, `name`, `email` on failure. No session is created |
| `GET /login` | Implemented — renders `login.html`; redirects to `/profile` if already signed in |
| `POST /login` | Implemented (Step 3) — verifies credentials, stores `user_id` in the session, redirects to `/profile`; re-renders with a generic `error` and `email` on failure |
| `GET /terms` | Implemented — renders `terms.html` |
| `GET /privacy` | Implemented — renders `privacy.html` |
| `GET /logout` | Implemented (Step 3) — clears the session, redirects to `/` |
| `GET /profile` | Implemented (Steps 4–6) — renders `profile.html` with the signed-in user's real data from `database/queries.py`; redirects to `/login` when signed out. Accepts optional `?start=YYYY-MM-DD&end=YYYY-MM-DD` (inclusive); blank = absent, invalid or reversed dates show an inline error and are ignored |
| `GET/POST /expenses/add` | Implemented (Step 7) — logged-in only (redirects to `/login` when signed out); GET renders `add_expense.html`, POST validates via `expense_validation.validate_expense_form()`, calls `create_expense()` and redirects to `/profile`; re-renders with `error` and the submitted values on failure |
| `GET/POST /expenses/<id>/edit` | Implemented (Step 8) — logged-in only (redirects to `/login` when signed out); `abort(404)` if the expense is missing or owned by another user (checked before validation); GET renders `edit_expense.html` pre-filled, POST validates via `validate_expense_form()`, calls `update_expense()` and redirects to `/profile`; re-renders with `error` and the submitted values on failure |
| `GET /expenses/<id>/delete` | Stub — Step 9 |

**Do not implement a stub route unless the active task explicitly targets that step.**

---

## Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection (it currently does — keep it)
- **Never hardcode the DB filename** — import `get_db()`; `DB_PATH` in `db.py` resolves to `expense_tracker.db` in the project root
- `get_db()` returns a new connection each call — always close it (`try/finally: conn.close()`)
- Importing `app.py` runs `init_db()` and `seed_db()`, so it creates/seeds the DB as a side effect (including under pytest)
- **Tests must not touch the real DB** — `tests/conftest.py` sets `database.db.DB_PATH` to a temp file *before* `from app import app`, because the import runs `init_db()`/`seed_db()`. Keep that ordering, and use the `app` fixture (it monkeypatches a fresh per-test DB)
- `app.secret_key` comes from the `SECRET_KEY` env var, with an insecure dev-only fallback. The session stores only `user_id`; a `before_request` loader sets `g.current_user` and templates get `current_user` (`None` when signed out or the id is stale)
- `get_user_by_email()` / `get_user_by_id()` in `db.py` return a `Row` or `None`; like `create_user()`, they do not normalise email — callers must `strip().lower()` first
- The app runs on **port 5001**, not the Flask default 5000 — don't change this
- The main branch is `master` (not `main`); `/create-spec` still says `main`, so adapt it