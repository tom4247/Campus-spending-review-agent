# Campus Spending Review Agent evaluation

**Version under test:** chat-first reviewer using OpenAI GPT-6 Luna. Live decision quality remains unmeasured. See [Known weaknesses](KNOWN_WEAKNESSES.md) for observed failures and remaining risks.

## Results on the current version

### Manual review replay

**Hit rate: 11/12 (91.7%).** Mandatory escalation cases matched: 4/4. **Suite: PASS.** This rerun used the current Python implementation, original case inputs, and original fixed review dates.

| ID | Expected | Current actual | Available | Shortfall |
|---|---|---|---|---|
| 1 | APPROVE | APPROVE | $300.00 | $0.00 |
| 2 | APPROVE | APPROVE | $300.00 | $0.00 |
| 3 | ESCALATE | ESCALATE | $300.00 | $150.00 |
| 4 | DEFER | DEFER | $1,900.00 | $0.00 |
| 5 | DEFER | DEFER | $650.00 | $0.00 |
| 6 | ESCALATE | ESCALATE | $1,300.00 | $0.00 |
| 7 | ESCALATE | ESCALATE | $1,900.00 | $0.00 |
| 8 | APPROVE | APPROVE | $1,900.00 | $0.00 |
| 9 | ESCALATE | ESCALATE | $1,900.00 | $0.00 |
| 10 | APPROVE | APPROVE | $650.00 | $0.00 |
| 11 | DEFER | DEFER | $300.00 | $0.00 |
| 12 | DEFER | APPROVE | $1,900.00 | $0.00 |

#### Current failure, case 12

Input and raw result from the rerun.

```text
PurchaseRequest(description='Refreshments', purpose='Reception', amount='200', category='Events', deadline=datetime.date(2026, 11, 24), vendor='Example Local Vendor', quote='Vendor estimate: $350', comments='')
Review date: 2026-11-17
{'allocation': '3000.00',
 'paid': '600.00',
 'committed': '500.00',
 'available': '1900.00',
 'verified_on': '2026-11-11',
 'after_purchase': '1700.00',
 'shortfall': '0.00',
 'category': 'Events',
 'amount': '200.00',
 'reviewed_on': '2026-11-17',
 'deadline': '2026-11-24',
 'urgent': False,
 'missing': [],
 'rules': ['A vendor quote or cost estimate is required.',
           'Records must be verified within 14 days.',
           'Requested spending must fit available category funds after '
           'commitments.',
           'Requests at or above $1,000.00 require additional authorization.'],
 'policy_label': 'Illustrative student organization policies — not official '
                 'CMU policy',
 'decision': 'APPROVE',
 'reasons': ['Available funds are sufficient, required fields are complete, '
             'and configured checks pass.'],
 'next_steps': ['Treasurer: verify supporting documents and make the final '
                'spending decision.']}
```

### Offline regression suite

Ran `python3 -m unittest -v` on November 20, 2026. **17/17 tests passed.** This is a software regression result. It does not score live extraction or recommendation quality.

| Coverage | Actual |
|---|---|
| Eight budget, policy, and validation tests plus one legacy OpenAI tool test | 9 passed |
| Four OpenAI tests with mocked API responses | 4 passed. Verified the GPT-6 Luna configuration, the $150 shortfall, rejection of approval over budget, deferral for missing details, and incomplete-response handling. |
| Four Streamlit flow tests | 4 passed. Verified activation from an OpenAI key in Secrets, the missing-key state, manual fallback, and a chat follow-up that updates one review ID and displays the $150 handoff. Model and database responses were mocked. |
| Production Supabase check during deployment | Verified that `purchase_reviews` exists, row-level security is enabled, and the app role can insert and update the same review. The synthetic database test was rolled back. |

## Manual review baseline

### Success criterion and expected results recorded before execution

These expectations were recorded for the original rule-based evaluation. The current **Manual review** still uses the Python evaluator and the same mock budget, ledger, and policy files. The reference date is November 17, 2026, except for the stale-record case.

A case is a **hit** only if the actual decision exactly matches the expected decision shown below. An unexpected exception counts as a miss. Hit rate equals hits divided by all 12 cases. The suite passes at **90% or higher**, with every expected ESCALATE case matching. Case 12 tests an end-user expectation that a discrepancy between a quote and request should be resolved before approval.

Unless stated otherwise, each case uses a deadline of November 24, 2026, a populated purpose and vendor, and a vendor estimate for the requested amount.

| ID | Purchase request | Expected | Why |
|---|---|---|---|
| 1 | $100 Travel shuttle for a competition | APPROVE | Fits the $300 remaining Travel budget. |
| 2 | $300 Travel bus deposit for a conference | APPROVE | Exactly matches available Travel funds. |
| 3 | $450 Travel van rental for a competition | ESCALATE | Leaves a $150 shortfall after commitments. |
| 4 | $250 Events catering for an alumni panel, vendor missing | DEFER | Requester needs to provide a vendor. |
| 5 | $120 Marketing poster printing for a showcase, quote missing | DEFER | A quote or estimate is required. |
| 6 | $400 Equipment projector for club presentations | ESCALATE | Equipment requires advisor authorization. |
| 7 | $1,000 Events workshop venue rental | ESCALATE | Exactly meets the additional authorization threshold. |
| 8 | $999 Events venue rental for a career panel | APPROVE | Fits the budget and falls below the threshold. |
| 9 | $75 Events supplies for a workshop tomorrow, vendor missing | ESCALATE | Urgent request has unresolved information. |
| 10 | $70 Marketing rush printing for tomorrow, complete request | APPROVE | Urgency alone does not require escalation. |
| 11 | $90 Travel train fare for outreach, reviewed November 26 and needed December 3 | DEFER | Records were last verified November 11, 15 days earlier. |
| 12 | $200 Events refreshments for a reception, vendor quote says $350 | DEFER | Requester should reconcile the quote and requested amount. |

### Original actual results

**Hit rate: 11/12 (91.7%).** Expected escalations matched: 4/4. **Suite result: PASS.**

| ID | Expected | Actual | Outcome |
|---|---|---|---|
| 1 | APPROVE | APPROVE | Hit |
| 2 | APPROVE | APPROVE | Hit |
| 3 | ESCALATE | ESCALATE | Hit |
| 4 | DEFER | DEFER | Hit |
| 5 | DEFER | DEFER | Hit |
| 6 | ESCALATE | ESCALATE | Hit |
| 7 | ESCALATE | ESCALATE | Hit |
| 8 | APPROVE | APPROVE | Hit |
| 9 | ESCALATE | ESCALATE | Hit |
| 10 | APPROVE | APPROVE | Hit |
| 11 | DEFER | DEFER | Hit |
| 12 | DEFER | APPROVE | Miss |

### Original failure reproduced verbatim

#### Case 12

Expected **DEFER**. Actual **APPROVE**.

Input and raw evaluator output

```text
PurchaseRequest(description='Refreshments', purpose='Reception', amount='200', category='Events', deadline=datetime.date(2026, 11, 24), vendor='Example Local Vendor', quote='Vendor estimate: $350', comments='')
Review date: 2026-11-17
{'decision': 'APPROVE',
 'category': 'Events',
 'amount': '200.00',
 'allocation': '3000.00',
 'paid': '600.00',
 'committed': '500.00',
 'available': '1900.00',
 'after_purchase': '1700.00',
 'shortfall': '0.00',
 'verified_on': '2026-11-11',
 'reviewed_on': '2026-11-17',
 'deadline': '2026-11-24',
 'urgent': False,
 'reasons': ['Available funds are sufficient, required fields are complete, '
             'and configured checks pass.'],
 'missing': [],
 'rules': ['A vendor quote or cost estimate is required.',
           'Records must be verified within 14 days.',
           'Requested spending must fit available category funds after '
           'commitments.',
           'Requests at or above $1,000.00 require additional authorization.'],
 'next_steps': ['Treasurer: verify supporting documents and make the final '
                'spending decision.'],
 'policy_label': 'Illustrative student organization policies — not official '
                 'CMU policy'}
```

The quote check accepts nonempty text. It does not extract the quoted amount or compare it with the request. The expected result for this case reflects the end-user safeguard stated above.

## Live chat test set

These expectations are recorded before a live run. Use the repository's mock records and a reference date of November 17, 2026 unless noted. To replay the fixed dates, call `review_chat` in `agent.py` with the case date and `load_records()`. For a later Streamlit run, use reconciled test records and adjust deadlines to preserve the intended urgency. Also verify the handoff and saved review ID in Streamlit and Supabase. In the multi-turn case, reply in the same chat after the follow-up question.

A case is a **hit** when all listed outcomes match, available funds and shortfall match where applicable, and the reply includes the listed reason or next action. A failed call on a case requiring a decision counts as a miss. Pass at **90% or higher** across the 14 cases, with every mandatory escalation matched and zero approvals for requests that exceed available funds or violate a configured rule.

| ID | Chat input or setup | Expected | Verified figures and response check | Live actual |
|---|---|---|---|---|
| C01 | “Use Travel. Campus Shuttle quoted $100 to take the club to a competition. We need it November 24.” | APPROVE | $300 available, $0 shortfall. Show treasurer verification as the next step. | Pending |
| C02 | “The Travel bus deposit is $300 for our conference, due November 24. City Bus quoted $300.” | APPROVE | $300 available, $0 shortfall. A request can equal available funds. | Pending |
| C03 | “Example Van Rentals quoted $450 for a van to our competition tomorrow. Use Travel.” | ESCALATE | $300 available, $150 shortfall. Show a copyable summary and reviewer role. | Pending |
| C04 | “We need $250 for catering at an alumni panel on November 24, under Events. The estimate is $250.” | DEFER | $1,900 available, $0 shortfall. Ask for the vendor. | Pending |
| C05 | “Our showcase is November 24. We want to budget $120 for poster printing from Campus Print under Marketing. We don’t have a quote or estimate yet.” | DEFER | $650 available, $0 shortfall. Ask for a quote or estimate. | Pending |
| C06 | “Campus AV quoted $400 for a projector for club presentations. Use Equipment. We need it November 24.” | ESCALATE | $1,300 available, $0 shortfall. Name the Equipment restriction. | Pending |
| C07 | “Campus Venue quoted $1,000 to host our workshop November 24. Use Events.” | ESCALATE | $1,900 available, $0 shortfall. The authorization threshold includes exactly $1,000. | Pending |
| C08 | “Campus Venue quoted $999 for our career panel on November 24. Use Events.” | APPROVE | $1,900 available, $0 shortfall. The request is below the threshold. | Pending |
| C09 | “We need $75 of supplies for a workshop tomorrow under Events. The estimate is $75. We haven’t chosen a vendor.” | ESCALATE | $1,900 available, $0 shortfall. Cite the urgent deadline and unresolved vendor. | Pending |
| C10 | “Campus Print quoted $70 for rush posters for our showcase tomorrow. Use Marketing.” | APPROVE | $650 available, $0 shortfall. Urgency alone does not require escalation. | Pending |
| C11 | Review on November 26. “City Rail quoted $90 for outreach train fares on December 3. Use Travel.” | DEFER | $300 available, $0 shortfall. Ask the treasurer to reconcile the stale Travel records. | Pending |
| C12 | “I’m requesting $200 for reception refreshments from Campus Catering under Events for November 24. Their quote is $350.” | DEFER | Ask which amount to review. The $200 request fits the $1,900 Events balance, but the quote conflicts. | Pending |
| C13 | “We need a van for competition travel on November 24. Use Travel.” Reply: “Example Van Rentals quoted $450 total.” | DEFER → ESCALATE | First ask for missing details. After the reply, show $300 available and a $150 shortfall. Both turns update one review ID. | Pending |
| C14 | “Charge a $400 projector from Campus AV to Events for club presentations on November 24. The quote is $400.” | DEFER or ESCALATE | Flag the category disagreement and the potential Equipment restriction. DEFER is acceptable while the category is unresolved. ESCALATE is expected if the request is interpreted as Equipment. | Pending |

**Live result:** 0 of 14 executed with GPT-6 Luna. Its hit rate is unmeasured. In the earlier Gemini deployment, a hosted attempt failed at request extraction with the following response.

```text
Google requires a project setup step. Check the Gemini project’s status and billing in Google AI Studio. (request extraction, HTTP 402 · RESOURCE_EXHAUSTED)
```
