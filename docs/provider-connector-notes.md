# Provider connector notes (living document)

Update this file whenever a connector's real-world behavior is confirmed or
changes -- it's the single place to check "does this actually work" before
trusting a nightly pull or debugging a discrepancy.

## Anthropic (`app/connectors/anthropic_connector.py`)

- Uses the Admin API: `GET /v1/organizations/usage_report/messages` (token
  usage) and `/v1/organizations/cost_report` (USD cost, not yet wired into the
  connector -- currently only usage is pulled and priced via our own
  `pricing_rates`, matching the "never trust a provider's own cost number as
  authoritative" principle).
- Requires a separate **Admin API key** (`sk-ant-admin-...`), created by an org
  admin -- a normal API key will not work.
- **Status as of 2026-09-18: field names confirmed against the live schema**
  at
  https://platform.claude.com/docs/en/api/beta/organization/usage_report/retrieve_messages,
  but still not live-verified against a real account/key. The response shape
  is `results[].model`, `results[].uncached_input_tokens`,
  `results[].output_tokens`, `results[].cache_read_input_tokens`, and
  `results[].cache_creation.{ephemeral_5m_input_tokens,ephemeral_1h_input_tokens}`
  (the latter two summed into one cache-write figure), with pagination via
  `has_more`/`next_page`. A previous version of this connector read
  `input_tokens` and a flat `cache_creation_input_tokens`, which don't exist
  in the real response -- that bug is fixed as of this pass.
- `pricing_rates.sku_code` must exactly match whatever model string the API
  returns (e.g. `claude-opus-5-input-tokens`) -- check a real response
  before configuring rates. See `backend/app/pricing_configs/` for a current
  snapshot of model pricing that follows this convention.

## OpenAI (`app/connectors/openai_connector.py`)

- Targets `GET /v1/organization/costs`. Community reports (see
  https://community.openai.com/t/v1-organization-costs-returning-404/1365618)
  show this endpoint 404s for some organizations even with a valid admin key --
  rollout has been inconsistent.
- **This connector actively probes the endpoint in `capabilities()`** rather
  than assuming a configured key means it works. If you configure
  `OPENAI_ADMIN_API_KEY` and `GET /api/connectors` still shows
  `supports_usage_pull: false`, that's expected for orgs without access -- use
  CSV import for OpenAI usage instead.
- ChatGPT Enterprise **seat** costs have no public consumption API as of the
  last research pass -- always CSV/manual entry, never pulled here.
- The cost endpoint reports pre-priced dollar amounts, not raw token counts.
  Current handling treats `amount.value` as the "quantity" with a `per_request`
  pass-through unit -- revisit this once a real response confirms whether a
  token-level usage endpoint is a better fit for pricing.

## Google (Gemini / Vertex AI) (`app/connectors/google_bigquery_connector.py`)

- There is no simple REST "usage cost" endpoint for Gemini/Vertex. The
  supported path is **Cloud Billing Detailed Data Export to BigQuery**
  (https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/detailed-usage),
  which the company confirmed is already enabled (or easy to enable).
- The connector queries `<project>.<dataset>.gcp_billing_export_resource_v1_*`
  filtered to `service.description IN ('Vertex AI', 'Generative Language API')`.
  **Re-verify the table naming and column schema** against Google's live docs
  before the first real pull -- schema/table suffixes can change.
- Configure via `GOOGLE_BIGQUERY_PROJECT` and `GOOGLE_BIGQUERY_BILLING_DATASET`
  env vars, plus standard Google auth (`GOOGLE_APPLICATION_CREDENTIALS`
  pointing at a service account JSON with BigQuery read access).

## General

- Every connector's `fetch_usage()` raises `ConnectorUnavailableError` when
  `capabilities().supports_usage_pull` is False -- callers (the manual pull
  endpoint, the nightly scheduler) must catch this and treat it as "use CSV
  instead," never as a crash.
- No connector computes cost. They only normalize provider data into
  `RawUsageRecord` (quantity + unit + sku_code + optional department hints);
  pricing and allocation always go through the same `costing_engine` /
  `allocation_service` regardless of whether usage arrived via API pull, CSV,
  or manual entry.
