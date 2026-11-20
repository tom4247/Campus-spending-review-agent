# Campus Organization Spending Review Agent

**One-page specification | Target design**

## Decision and authority

The **OpenAI model selects the purchase recommendation** after reviewing the request, verified financial facts, and configured policy. It chooses **APPROVE**, **DEFER**, or **ESCALATE** and explains why. Python calculates financial facts, validates records, and checks that the model's output is safe to display. The treasurer or designated reviewer makes the final spending decision.

## Inputs and decision flow

1. A requester submits a purchase description, purpose, USD amount, category, needed-by date, vendor, and quote or estimate. A natural-language draft is optional. The requester confirms extracted details.
2. Python validates the submission and reads the mock budgets, ledger, and policies. It calculates available funds as **allocation − paid expenses − outstanding commitments**, plus the projected balance and any shortfall.
3. OpenAI receives the relevant request details and uses a read-only tool to retrieve the verified facts and applicable policy. It returns a structured recommendation with reasons, supporting evidence, and the next action.
4. Streamlit validates and displays the recommendation alongside the underlying facts. If the model call fails or its response violates a mandatory rule, the app displays **Review unavailable** and directs the requester to a human reviewer.

## Outcomes

| Model recommendation | Meaning | Next action |
|---|---|---|
| **APPROVE** | The request is ready for treasurer review. Funds are sufficient, the evidence is complete, and applicable rules are satisfied. | Treasurer verifies the request and decides whether to authorize spending. |
| **DEFER** | The requester can resolve missing or conflicting information, or the treasurer needs to reconcile stale records. | Resolve the named issue and resubmit. |
| **ESCALATE** | A shortfall, restriction, authorization threshold, urgency with an unresolved issue, or policy ambiguity calls for human judgment. | Send the review summary to the named advisor or designated financial reviewer before committing funds. |

Configured escalation takes precedence over deferral. The sample policy uses an inclusive $1,000 threshold, requires advisor authorization for Equipment, treats today and tomorrow as urgent, and requires records verified within 14 days. These policies are illustrative.

## Boundaries and evaluation

The model can read the evidence needed for review. It has no authority to spend, approve on behalf of the organization, change records, or grant exceptions. The first handoff is manual. Streamlit provides the contact or role and a summary the requester can share. Missing credentials or failed validation leave the recommendation unavailable and the human review path visible.

Acceptance tests cover recommendation accuracy, mandatory escalation, quote and category ambiguity, evidence grounding, and failure handling. The existing 12-case evaluation measures the current Python decision engine. The model-led design requires a new evaluation run.

**Implementation status:** The current code still selects recommendations in Python. OpenAI optionally drafts requests and explains decisions. The README documents the model-led architecture and migration.
