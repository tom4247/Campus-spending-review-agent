# Campus Organization Spending Review Agent

A local decision-support prototype for student organization treasurers. All data is mock and all policies are illustrative, **not official CMU policy**. APPROVE is a recommendation only. The app has no payment, authorization, or budget-writing capability.

## Architecture

```text
app.py                 Streamlit form, budget overview, recommendation
review.py              Read-only CSV loading, validation, Decimal calculations, policy checks
agent.py               OpenAI Responses API explanation and read-only tool
data/budgets.csv       Category allocations and reconciliation dates
data/ledger.csv        Paid expenses and outstanding commitments
data/policies.json     Configurable illustrative rules
test_review.py         Financial, decision, data validation, and mocked API tests
requirements.txt       Python dependencies
.env.example           Optional API configuration template
```

The user selects the category or confirms a category suggested by the optional AI draft. Python loads and validates the source files, calculates `available = allocation - paid - commitments`, checks completeness, record freshness, restrictions, and approval thresholds, and selects a recommendation. Decimal arithmetic avoids floating-point currency errors.

Escalation takes priority: a shortfall, restriction, threshold requiring authorization, or urgent unresolved information produces ESCALATE. Other missing information or stale records produces DEFER. Otherwise the recommendation is APPROVE. Urgency alone does not escalate an otherwise complete, compliant request. The authorization threshold is inclusive.

When AI is enabled, the model must call `get_verified_review`, a narrowly defined, read-only tool returning the Python review snapshot. A second model response explains that result. It receives no filesystem access, write tools, raw purchase text, or authority over the decision. The UI always displays Python's result separately. Generated commentary remains fallible; it cannot override the authoritative recommendation. The pattern follows the [official OpenAI function calling documentation](https://developers.openai.com/api/docs/guides/function-calling).

## Install and run

Requires Python 3.11 or newer. Open a terminal in this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501. Stop with Ctrl+C. The initial review works without an API key.

For optional live AI explanations:

```bash
cp .env.example .env
```

Edit `.env` to supply your own `OPENAI_API_KEY` and, if needed, a model your account can access. The sample model is `gpt-4.1-mini`; model access is account dependent. Restart Streamlit after editing configuration, then enable **Add OpenAI explanation** in the sidebar. API calls may incur usage charges. Never commit `.env`. With missing credentials, API errors, or timeouts the app retains its deterministic review and shows a fallback notice.

To draft a request with the configured API key, open **Draft with AI**, describe the purchase, and click **Draft request**. The draft text is sent to OpenAI. Check the suggested fields, fill in missing details, and confirm the category and date before submitting for a rule-based review.

## Try the example

Click **Try a sample request** to fill in a $450 van request. Travel allocation is $2,000 minus $800 paid = $1,200 before commitments. The $900 hotel commitment leaves $300, so the shortfall is $150. The deadline defaults to tomorrow. Select **Review purchase** to see ESCALATE and next steps.

To see APPROVE, use a $100 Travel request with all fields completed and current records. To see DEFER, leave the vendor blank, use a $100 request, and choose a deadline a week away. An urgent request with missing information escalates.

Sample records were verified on **November 11, 2026**. After 14 days they intentionally become stale. Update `verified_on` only after reconciling the entire category, including commitments; do not automatically refresh it when the app starts. The real current date drives review freshness and deadlines.

## Configure data and policies

Each budget category must be unique. Each ledger ID must be unique across paid and committed entries. When a commitment is paid, change its status to `paid`; do not retain a second committed row for the same obligation. Use USD amounts with at most two decimal places and no dollar signs or thousands separators in CSVs. `verified_on` uses ISO `YYYY-MM-DD`. A category with no ledger entries has zero recorded expenses and commitments; reconciliation must establish that the file is complete.

In `policies.json`, configure the inclusive `approval_threshold`, maximum record age, urgent window, quote requirement, category restrictions, and human escalation authority. A restriction always requires human review; there is no automatic exception approval. Unknown categories/statuses, duplicate IDs/categories, malformed or missing files, and invalid amounts block reviews. Negative available balances are shown rather than hidden. Missing request details and stale or future-dated records prevent an APPROVE recommendation.

## Validation

```bash
python -m unittest -v
```

Tests cover the $150 shortfall, exact budget boundary, all three outcomes, urgent missing information, stale/future records, threshold and restriction checks, duplicate ledger IDs, invalid amounts, deadlines, and the mocked OpenAI tool exchange. No API key is needed for tests.

## What works and what remains

Implemented: local dashboard, read-only sample records, deterministic financial and policy review, configurable policies, next steps, optional live AI explanations, and offline fallback. The application does not simulate a successful AI call when no key is configured. Live API behavior requires your credentials and has not been verified by offline tests.

Simulated: financial records, quotes, vendors, reconciliation dates, and organizational rules. The app checks that a quote exists; it does not parse or authenticate it, compare its amount with the request, verify vendor identity, or infer restrictions from free text. Purpose, comments, and category accuracy require human review. Duplicate IDs are detected; differently identified entries representing the same real-world obligation require reconciliation. There is no persistent request history or document upload.

Next development: test representative requests with treasurers, obtain and encode organization-approved policies, add document/quote verification with human confirmation, improve reconciliation, and evaluate model explanations against a labeled set. A practical three-week sequence is core prototype and sample scenarios in week one, policy validation and usability work in week two, and scenario testing and demonstration preparation in week three. No database, accounts, or deployment infrastructure is needed for this MVP.
