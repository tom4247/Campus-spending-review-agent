# Campus Organization Spending Review Agent

**One-page specification | Chat-first prototype**

## What it does

A requester describes a purchase in chat. OpenAI extracts the request and researches public provider prices. Python calculates **available funds = allocation − paid expenses − outstanding commitments**. For routine purchases, a comparable published estimate can support a recommendation when the price is close and the costs fit the budget. The agent labels its assumptions. Date-sensitive or materially uncertain purchases need firmer prices and terms before approval.

| Decision | What happens next |
|---|---|
| **APPROVE** | The request is ready for routine treasurer verification and authorization. |
| **DEFER** | The model asks a specific follow-up question. The requester can reply in the same chat to correct or complete the request. Stale records require reconciliation. |
| **ESCALATE** | The app shows a copyable summary with the request, available funds, verified policy triggers, and who should review it. The requester shares it with the authorized reviewer. |

The sample policy requires additional authorization for requests **at or above $1,000**, advisor review for Equipment, and a quote or estimate. Records must be verified within 14 days. A request due today or tomorrow escalates when information is unresolved. Mandatory escalation takes precedence over deferral.

## Interface and records

Chat is the main interface. **Manual review** opens the rule-based form and works while chat is paused or unavailable. To activate OpenAI chat with GPT-6 Luna, set a working `OPENAI_API_KEY` in Streamlit Secrets. Set `OPENAI_CHAT_ENABLED = false` to pause chat.

The requester can adjust an allocation by typing `Update the Travel budget to $2,200`, or record a paid expense directly by typing `We spent $300 on Travel`. They can also report what they paid for the active reviewed purchase. Each paid entry updates the balance for later requests in the same browser session.

With Supabase configured, each request gets a `purchase_reviews` row with its latest recommendation, budget snapshot, and any reported payment. Budget adjustments and direct expenses are recorded in `purchase_submissions`. Streamlit shows review history and updated balances for the current session.

## Boundaries and evaluation

The prototype uses synthetic records and illustrative policies. Authorized people handle spending approval, purchases, payments, ledger changes, and exceptions. The agent produces and records a recommendation. The requester handles escalation delivery.

In a hosted trial, 12 of 12 comparable decision labels matched, including all four comparable mandatory escalations. All 14 prompts shared one chat. The original 14-case hit rate remains unverified because it requires budget evidence and specific stale-record and two-turn checks. The [evaluation](AGENT_EVALUATION.md) includes the observed outcomes, a manual-review score of 11/12, and 33 passing local automated tests. See [known weaknesses](KNOWN_WEAKNESSES.md) for reproduced issues.
