# Campus Organization Spending Review Agent

**One-page specification | Chat-first prototype**

## What it does

A requester describes one proposed purchase in chat. OpenAI extracts the item, purpose, USD amount, spending category, needed-by date, vendor, and quote. Python reads the synthetic budget, ledger, and policy records and calculates **available funds = allocation − paid expenses − outstanding commitments**. The model uses those verified facts to choose a recommendation and explain it. Python limits the available outcomes when a mandatory rule applies or required evidence is missing.

| Decision | What happens next |
|---|---|
| **APPROVE** | The request is ready for routine treasurer verification and authorization. |
| **DEFER** | The model asks a specific follow-up question. The requester can reply in the same chat to correct or complete the request. Stale records require reconciliation. |
| **ESCALATE** | The app shows a copyable summary with the request, available funds, verified policy triggers, and who should review it. The requester shares it with the authorized reviewer. |

The sample policy requires additional authorization for requests **at or above $1,000**, advisor review for Equipment, and a quote or estimate. Records must be verified within 14 days. A request due today or tomorrow escalates when information is unresolved. Mandatory escalation takes precedence over deferral.

## Interface and records

Chat is the main interface. **Manual review** opens the rule-based form and works while chat is paused or unavailable. To activate OpenAI chat with GPT-6 Luna, set a working `OPENAI_API_KEY` in Streamlit Secrets. Set `OPENAI_CHAT_ENABLED = false` to pause chat.

With Supabase configured, each new chat request gets one `purchase_reviews` row. Follow-ups update its transcript, latest status, verified budget snapshot, and next action. Streamlit shows history for the current session. Project administrators can inspect past sessions in Supabase. Manual form inputs are logged separately in `purchase_submissions`.

## Boundaries and evaluation

The prototype uses synthetic records and illustrative policies. Authorized people handle spending approval, purchases, payments, ledger changes, and exceptions. The agent produces and records a recommendation. The requester handles escalation delivery.

The [evaluation](AGENT_EVALUATION.md) reports the manual-policy replay, offline chat checks, and the prepared live chat test set. The [known weaknesses](KNOWN_WEAKNESSES.md) identify which issues were reproduced and which still require live testing.
