# Campus Organization Spending Review Agent

**One-page specification | Chat spending review**

## What the agent decides

The **Gemini chat agent reviews one proposed expense at a time and returns APPROVE, DEFER, or ESCALATE**. An APPROVE completes the agent's routine review. Under the project proposal, the treasurer verifies the result and authorizes spending before committing funds. An ESCALATE identifies the person or body that can resolve an exception or give additional approval.

## Inputs and workflow

1. A member describes the purchase in chat, including the purpose, total, vendor, quote, and deadline when available. Gemini extracts the details, and the member can clarify them in a follow-up message.
2. Python validates the source records and prepares verified facts from the synthetic budgets, ledger, and spending rules. Available funds equal **allocation − paid expenses − outstanding commitments**.
3. Gemini receives the verified evidence and selects an outcome with a concise reason. Required escalations and unresolved required fields constrain the outcomes the app accepts.
4. Streamlit displays the accepted outcome and calculation. Invalid model output, unavailable evidence, and service failures surface **Review unavailable** with a human review path.

## Outcomes

| Agent decision | When it applies | Next action |
|---|---|---|
| **APPROVE** | The expense fits the verified budget, required evidence is complete, and applicable rules are satisfied. | Proceed to routine treasurer verification and authorization. |
| **DEFER** | A missing quote, conflicting amount, uncertain category, or stale record needs clarification and can be resolved before the deadline. | Resolve the named issue and resubmit. |
| **ESCALATE** | A shortfall, restriction, threshold, policy ambiguity, or urgent unresolved issue requires human judgment. | Share the review summary with the authorized advisor or designated financial reviewer. |

A $450 Travel van rental with $300 available after commitments has a $150 shortfall. The agent should return **ESCALATE** and explain who can review a possible transfer or supplemental funding. The mock policies include an inclusive $1,000 authorization threshold, extra authorization for Equipment, and a 14-day record freshness limit.

## Scope and evaluation

The agent issues the review decision. The organization's authorized people handle orders, payments, changes to the budget, and policy exceptions. Escalation handoff is manual. The prototype uses synthetic records and illustrative spending policies.

Evaluate at least 10 synthetic cases with expected outcomes and balances recorded in advance. Check the decision, available-funds calculation, and supporting explanation. Flag missing or conflicting evidence. Any approval that exceeds available funds or violates a stated rule fails the proposal's safety criterion.

**Implementation status:** Set `GEMINI_API_KEY` to enable chat. The separate purchase form uses Python to select outcomes, with optional OpenAI drafting and explanations. The existing 12-case evaluation measures the Python baseline.
