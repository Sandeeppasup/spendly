# CLAUDE.md

## Project overview

Spendly is a lightweight personal expense tracker built with Flask and SQLite.

---

## Architecture
```
spendly/
├── app.py              # All routes — single file, no blueprints
├── expense_tracker.db  # SQLite file (gitignored), created by init_db()
├── database/
│   └── db.py           # SQLite helpers: get_db(), init_db(), seed_db(), create_user(), DB_PATH, CATEGORIES
├── templates/
│   ├── base.html       # Shared layout — all templates must extend this
│   └── *.html          # One template per page (landing, login, register, terms, privacy)
├── static/
│   ├── css/
│   │   ├── style.css       # Global styles
│   │   └── landing.css     # Landing-page-only styles
│   └── js/
│       └── main.js         # Vanilla JS only
├── .claude/
│   ├── commands/       # Project slash commands: /create-spec, /seed-user, /seed-expense
│   └── specs/          # Feature specs: 01-database-setup.md, 02-registration.md
├── tests/
│   ├── conftest.py     # Redirects DB_PATH to a temp file; provides the `app` fixture
│   └── test_registration.py
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
- Always use a subagent to verify test results 
  after any implementation
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
| `GET /login` | Implemented — renders `login.html` (`POST /login` is Step 3; `login.html` still has a hardcoded `action="/login"` to fix then) |
| `GET /terms` | Implemented — renders `terms.html` |
| `GET /privacy` | Implemented — renders `privacy.html` |
| `GET /logout` | Stub — Step 3 |
| `GET /profile` | Stub — Step 4 |
| `GET /expenses/add` | Stub — Step 7 |
| `GET /expenses/<id>/edit` | Stub — Step 8 |
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
- No `secret_key` is configured yet, so Flask sessions and `flash()` don't work until Step 3 adds one
- The app runs on **port 5001**, not the Flask default 5000 — don't change this
- The main branch is `master` (not `main`); `/create-spec` still says `main`, so adapt it