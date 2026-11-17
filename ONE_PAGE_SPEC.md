# Campus Organization Spending Review Agent

**One-page specification | Local decision-support prototype**

## Decision it supports
Helps a student organization treasurer decide whether a proposed purchase is ready for human approval, needs more information, or requires additional review. It checks available category funds, outstanding commitments, required request details, record freshness, and configured spending rules. All records are mock and all policies are illustrative—not official CMU policy.

## Inputs
- **Purchase request:** description, purpose, USD amount, user-selected budget category, date needed, vendor, quote or cost-estimate text, and optional comments.
- **Budget records:** category allocations and dates when each category was last reconciled (`data/budgets.csv`).
- **Ledger:** paid expenses and outstanding commitments, each with a unique ID, category, description, amount, and status (`data/ledger.csv`).
- **Policy configuration:** authorization threshold, record-age limit, urgency window, quote requirement, restricted categories, and escalation authority (`data/policies.json`). The current date drives freshness and deadline checks.

## Outputs
One recommendation, with reasons, applied rules, missing information, and next steps:
- **APPROVE:** funds are sufficient, required fields are complete, records are current, and configured checks pass. This is a recommendation only.
- **DEFER:** information is missing or records need verification, with no condition requiring escalation.
- **ESCALATE:** funds are insufficient, a category restriction applies, the authorization threshold is met, or an urgent deadline coincides with unresolved information. Escalation takes priority over deferral.

The review shows allocation, paid expenses, commitments, available funds, projected balance after purchase, shortfall, and review/verification dates. Available funds equal **allocation − paid expenses − outstanding commitments**. Python performs currency calculations and selects the recommendation. An optional AI explanation summarizes the verified result; the underlying review remains visible and works if AI is unavailable.

**Current sample rules:** requests of $1,000 or more need additional authorization; Equipment purchases need advisor authorization; records must be verified within 14 days; a quote or estimate is required; a deadline today or tomorrow is urgent.

## What it refuses to do
- Authorize purchases, send payments, commit funds, or change budgets or ledger records.
- Return an APPROVE recommendation when required information is missing, records are stale or future-dated, or configured escalation conditions apply. Malformed or inconsistent source data blocks review.
- Let the AI choose or override the recommendation, perform financial calculations, invent policies, access files, or execute write actions. Its only tool retrieves the verified review.
- Treat illustrative rules as official university policy or grant exceptions to restrictions.

**Review limits:** it checks that quote text is present, but does not authenticate documents, verify vendors, compare quoted and requested amounts, infer restrictions from free text, or judge the accuracy of the selected category and stated purpose. Different ledger IDs can still represent the same obligation; human reconciliation is required.

## Human in the loop
The **treasurer** supplies the request, selects the category, reconciles records and commitments, verifies supporting documents and purpose, and makes the final spending decision—even after APPROVE. For ESCALATE, the treasurer contacts the **organization advisor or designated financial reviewer** before committing funds. For DEFER, the treasurer resolves missing information or verifies records and reruns the review. Any AI commentary is fallible and must be checked against the displayed Python review.
