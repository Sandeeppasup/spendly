# Spec: Date Filter for Profile Page

## Overview
Step 6 lets a signed-in user narrow the profile page to a date range. Today
`/profile` always aggregates every expense the user has ever logged. This step
adds a "From / To" filter (plus quick presets such as "This month") that
scopes the summary stats, the transaction history and the category breakdown
to the chosen range. The filter is carried in the query string so a filtered
view can be bookmarked and survives a refresh. It builds directly on the
query helpers introduced in Step 5 and prepares the page for the add, edit
and delete steps that follow.

## Depends on
- Step 1: Database setup (`expenses.date` stored as ISO `YYYY-MM-DD` text)
- Step 3: Login / Logout (`g.current_user`, session)
- Step 4: Profile page static UI (`profile.html`, `profile.css`)
- Step 5: Profile backend routes (`database/queries.py` helpers)

## Routes
No new routes. The existing `GET /profile` route accepts two optional query
parameters:
- `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` — same page, scoped to the
  inclusive date range — logged-in
  - Either parameter may be supplied alone (open-ended range).
  - No parameters = all time (current behaviour).
  - Blank, malformed or impossible dates (e.g. `2026-02-31`) are treated as
    absent and an inline error message is shown; the page never returns a 500.
  - If `start` is after `end`, show an inline error and fall back to the
    unfiltered view.

## Database changes
No database changes. `expenses.date` is already ISO text, so `date >= ?` and
`date <= ?` comparisons work lexically. (Verified against `database/db.py`.)

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter bar above the stats row: a GET `<form>` with two
    `<input type="date">` fields (From, To), an "Apply" button and a "Clear"
    link, all using `url_for('profile')`.
  - Add preset links: "This month", "Last 30 days", "All time", built in the
    route (not hardcoded URLs) and passed to the template.
  - Inputs are pre-filled with the active `start` / `end`; the active preset
    is visually marked.
  - Show the inline validation error when present.
  - Show a heading note such as "Showing 01 Nov 2026 – 10 Nov 2026" when a
    filter is active.
  - Empty state text becomes "No expenses in this period." when filtered
    (keep "No expenses yet." for the unfiltered case).

## Files to change
- `app.py` — parse and validate `start` / `end` in `profile()` (via a small
  private helper), pass them to the query helpers and the template
- `database/queries.py` — `get_summary_stats`, `get_recent_transactions` and
  `get_category_breakdown` gain optional `start=None, end=None` arguments
  that add parameterised `AND date >= ?` / `AND date <= ?` clauses
- `templates/profile.html` — filter bar, preset links, error and empty states
- `static/css/profile.css` — styles for the filter bar
- `CLAUDE.md` — update the `/profile` row and the `queries.py` description

## Files to create
- `date_filters.py` — Flask-aware helpers for the filter (`parse_date_range`,
  `format_range_label`, `build_presets`), kept out of `app.py` so the route
  stays thin
- `tests/test_profile_date_filter.py` — unit tests for the filtered query
  helpers and route tests for `/profile` with query parameters
- `.claude/specs/06-date-filter-profile-page.md` — this spec

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — build the optional clauses from fixed strings
  and pass dates as `?` values; never format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline `<style>` tags; styles go in `profile.css`
- Vanilla JS only, and none is required: the form must work with JS disabled
- Use `url_for()` for every link, including presets and Clear
- Validate dates with `datetime.strptime(value, "%Y-%m-%d")`; keep that logic
  in `date_filters.py`, and keep SQL only in `database/queries.py`
- Existing signatures must stay backward compatible (`start` / `end` default
  to `None`) so Step 5 tests keep passing
- `get_recent_transactions` keeps its `limit` (default 10) within the filtered
  range
- Summary, transactions and breakdown must all use the same range so the
  numbers on the page agree
- An empty range returns zeros / empty lists, never an exception
- Currency stays ₹
- Do not implement the add / edit / delete stub routes

## Definition of done
- [ ] Visiting `/profile` with no parameters looks and behaves exactly as in Step 5 (₹6,939.25 total, 8 transactions for the seed user)
- [ ] The filter bar shows From and To date inputs, an Apply button and a Clear link
- [ ] Setting From and To and clicking Apply updates the URL to `/profile?start=...&end=...` and the inputs stay filled
- [ ] Total spent, transaction count, top category, the transaction table and the category breakdown all reflect only expenses inside the range, inclusive of both end dates
- [ ] A range containing no expenses shows ₹0.00, 0 transactions, an empty breakdown and "No expenses in this period."
- [ ] Supplying only From or only To filters open-endedly
- [ ] "This month", "Last 30 days" and "All time" presets apply the expected ranges and the active one is highlighted
- [ ] "Clear" returns to the unfiltered view
- [ ] `?start=garbage`, `?end=2026-02-31` and `?start=2026-11-10&end=2026-11-01` show an inline error and do not crash (no 500)
- [ ] A SQL-injection attempt such as `?start=' OR 1=1 --` is rejected as an invalid date
- [ ] Signed-out visits to `/profile?start=...` still redirect to `/login`
- [ ] A different user never sees the first user's expenses under any filter
- [ ] `pytest` passes, including the new `tests/test_profile_date_filter.py`
