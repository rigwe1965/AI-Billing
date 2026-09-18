# AI Spend Management

Tracks and allocates monthly AI provider spend (Anthropic, OpenAI, Google, and custom
providers) across departments, with a deterministic, auditable costing engine — no
cost figure is ever estimated by an LLM. See `docs/` and the build plan for full
architecture. **All 4 phases plus the frontend are built**: core data model, CSV
ingestion, costing engine, auth/roles, multi-department allocation, provider API
connectors, budgets/alerts, Excel/PDF exports, and a React dashboard.

## Backend setup

```
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
alembic upgrade head
python seed.py                  # creates starter providers, departments, and an admin login
python load_pricing_configs.py  # seeds current-generation model pricing (see below)
uvicorn app.main:app --reload --port 8000
```

The seed script prints the initial admin email/password (defaults to
`admin@ai-billing.app` / `changeme123` unless `ADMIN_INITIAL_EMAIL` /
`ADMIN_INITIAL_PASSWORD` env vars are set) — log in and change it, then create
real users via `POST /api/users` (admin_finance only).

## Auth

`POST /api/auth/login` sets an httpOnly session cookie; `POST /api/auth/logout`
clears it; `GET /api/auth/me` returns the current user. Two roles:
- `admin_finance` — sees all departments, manages users/pricing/allocation mappings.
- `dept_lead` — scoped to their own department for costs/usage; CSV imports are
  rejected if they specify a different department's `department_code`.

## Department allocation

Three ways a usage row ends up attributed to a department, in this order:
1. **Direct** — `department_code` set on the CSV row (or usage_record already has one).
2. **Key mapping** — `POST /api/allocations/api-key-map` maps an `api_key_label` to a department.
3. **Tag mapping** — `POST /api/allocations/tag-map` maps a `tag_value` (project/customer id) to a department.
4. **Manual split** — `POST /api/allocations/manual` splits one usage_record's cost across departments by percentage (admin only), for usage that doesn't fit the above.

Usage that matches none of these shows up at `GET /api/costs/needs-allocation`
(admin only) rather than being silently assigned. After adding a new key/tag
mapping, `POST /api/allocations/reprocess-unallocated` retroactively re-resolves
any usage still stuck in that state.

## Provider API connectors

Optional -- unset credentials just make a connector report itself unavailable,
never crash. Set via environment variables (or `backend/.env`):

| Provider | Env vars |
|---|---|
| Anthropic | `ANTHROPIC_ADMIN_API_KEY` (an Admin API key, `sk-ant-admin-...`, not a regular key) |
| Anthropic (AI Insights) | `ANTHROPIC_API_KEY` (a normal Messages API key — separate from the Admin key above; powers `POST /api/insights/ask`, see the AI Insights section below) |
| OpenAI | `OPENAI_ADMIN_API_KEY`, `OPENAI_ORG_ID` |
| Google (Gemini/Vertex) | `GOOGLE_BIGQUERY_PROJECT`, `GOOGLE_BIGQUERY_BILLING_DATASET`, plus standard `GOOGLE_APPLICATION_CREDENTIALS` — requires Cloud Billing Detailed Data Export to BigQuery already enabled |

Admin-only endpoints:
- `GET /api/connectors` — capability status per provider (configured? can pull? why not?).
- `POST /api/connectors/{provider_code}/test-connection` — checks credentials work.
- `POST /api/connectors/{provider_code}/pull` (body: `period_start`, `period_end`) — triggers an on-demand pull; also runs automatically every night at 02:00 for any provider whose connector reports `supports_usage_pull: true`.

OpenAI's usage/costs API has had inconsistent availability across
organizations — see `docs/provider-connector-notes.md` for what's confirmed vs.
still uncertain per provider. A connector that can't pull always falls back
cleanly to CSV import; it never guesses.

## Budgets and alerts

Admin creates a monthly budget per department (default alert thresholds 80%
and 100%, customizable):

```
POST /api/budgets
{"department_code": "ENG", "period": "2026-01", "amount": 5000, "threshold_percents": [80, 100]}
```

- `GET /api/budgets/status` — current spend vs. budget for every budget the
  caller can see (dept_lead: own department only; admin: all).
- `GET /api/budgets/alerts?open_only=true` — fired alerts; each threshold fires
  **exactly once** per budget/period no matter how many times spend is
  re-evaluated (deduplicated via a unique constraint).
- `POST /api/budgets/alerts/{id}/acknowledge` — marks an alert acknowledged.

Thresholds are checked immediately after every CSV import, connector pull, and
manual allocation change, plus nightly at 02:30 as a safety net. **v1 ships
in-app notifications only** — the `Alert` row itself, surfaced via the API
above, is the notification. `app/services/notification_service.py` defines a
pluggable `EmailNotificationChannel` stub for later; it is intentionally not
wired to a real mail provider yet.

## Reports

- `GET /api/reports/excel` — summary + line-item detail workbook (.xlsx),
  including audit columns (pricing rate id/effective date, usage source, needs
  attention flags).
- `GET /api/reports/pdf` — printable summary with a department/provider spend
  table and budget-status table.

Both are scoped like everything else: a `dept_lead` gets a report containing
only their own department's data.

## Frontend setup

```
cd frontend
npm install
npm run dev          # http://localhost:5173, expects the backend on :8000
```

Log in with the admin credentials from the seed script. Pages:
- **Dashboard** — total spend, spend by department/provider (bar charts), monthly
  trend by department (line chart), budget status bars, and a "needs attention"
  banner for unpriced/unallocated usage. A `dept_lead` sees only their own
  department everywhere; `admin_finance` sees everything.
- **Usage Import** — CSV upload.
- **Budgets & Alerts** — create budgets (admin), view status, acknowledge alerts.
- **Reports** — download Excel/PDF.
- **Insights** — ask natural-language questions about your spend; answers are
  AI-generated commentary, not authoritative cost figures.
- **Pricing Rates**, **Allocation Mapping**, **Provider Connectors**, **Users &
  Departments** — admin-only.

Set `VITE_API_BASE` (in `frontend/.env`) if the backend isn't at
`http://localhost:8000`. Chart colors follow a colorblind-validated categorical
palette (`frontend/src/theme/palette.ts`) with light/dark mode support
(`frontend/src/index.css`).

**Note on verification:** the frontend was verified via `tsc --noEmit`, a
production `npm run build`, and HTTP-level checks (CORS preflight, cookie
`Set-Cookie`/`SameSite` behavior against the real backend) confirming the
browser's fetch+cookie flow will work end-to-end — but it was not visually
click-tested in an actual browser in this environment. Open
`http://localhost:5173` yourself to confirm the UI renders and behaves as
expected before relying on it.

## Running tests

```
cd backend
.venv\Scripts\activate
python -m pytest tests/ -v
```

## CSV import format

Upload via `POST /api/usage/import-csv` (multipart form field `file`, requires
login). Required columns: `provider_code, sku_code, quantity, unit, period_start,
period_end`. Optional: `department_code, tag_value, api_key_label`. See
`backend/tests/fixtures/csv/` for an example.

Pricing rates must be added via `POST /api/pricing` before usage for a given
provider/sku can be costed — usage without a matching rate is surfaced at
`GET /api/costs/unpriced` rather than being priced with a guess.

## Model/pricing catalog

`backend/app/pricing_configs/*.yaml` holds a dated snapshot of
current-generation model pricing per provider (Anthropic, OpenAI, Google).
`python load_pricing_configs.py` loads them into `pricing_rates` using the
same versioned upsert rule as `POST /api/pricing` (old rows are closed, never
overwritten) — safe to re-run. **Prices change over time and these are a
point-in-time snapshot** — re-verify against each provider's live pricing
page before trusting them for real billing, and add a new dated YAML file
(never edit an already-loaded one) when prices change.

## AI Insights

`POST /api/insights/ask` (any authenticated user) answers natural-language
questions about spend by handing an LLM the same already-computed figures
`/api/costs/summary`, `/api/costs/unpriced`, and `/api/budgets/status` return
for that caller — a dept_lead's question is scoped to their own department
exactly like those endpoints. The answer is advisory commentary, never a
source of truth for a cost figure — the app's deterministic costing engine
(`app/services/costing_engine.py`) is the only thing that ever computes a
number that gets stored. Requires `ANTHROPIC_API_KEY` (a normal Messages API
key — distinct from `ANTHROPIC_ADMIN_API_KEY` above, which is Admin-API/
billing-only); without it the endpoint returns `503` rather than crashing.
The frontend's **Insights** page is a simple Q&A panel over this endpoint.
