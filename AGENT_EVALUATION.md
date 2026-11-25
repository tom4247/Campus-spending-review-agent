# Campus Spending Review Agent evaluation

The tested version was the chat-first OpenAI deployment at `e90d812`, using GPT-6 Luna by default. The project team submitted 14 prompts to the hosted Streamlit app on November 20, 2026. Supabase confirmed that the prompts and replies were recorded in one conversation.

## Results summary

| Evaluation | Result |
|---|---|
| [Hosted chatbot trial](#live-chat-test-set) | **12/12 (100%) decision-label matches** on comparable prompts, including 4/4 expected escalations. Two prompts differed from the planned setup. |
| [Preregistered hosted criteria](#preregistered-success-criterion) | **Full-suite hit rate unavailable.** The trial used one chat, and only the final structured budget snapshot was available in Supabase. |
| [Manual review replay](#manual-review-replay) | **11/12 hits (91.7%), PASS** under the original manual-review criterion. It approved a $200 request with a conflicting $350 quote. |
| [Offline regression suite](#offline-regression-suite) | **19/19 passed**, including stale-record handling in Python and a two-turn Streamlit handoff with mocked responses. |

The [known weaknesses](KNOWN_WEAKNESSES.md) document explains the implications for requesters and treasurers.

## Local budget and payment verification

On November 25, 2026, all **25 automated tests passed**. The Streamlit tests mocked OpenAI and Supabase. They verified that a reported $125.50 payment on a $100 quote lowered the Travel balance from $300 to $174.50. Repeating the confirmation retried a failed Supabase save without deducting it twice. A later $200 request showed a $25.50 shortfall, and a fresh session started with $300. A separate test updated the allocation, matched a named $300 payment to the current van rental, and adjusted the balance again in the same conversation. Starting a fresh chat with “We spent $300 on travel” brought the available balance to $0. A completed $300 Zipcar rental was also logged while a proposed purchase review was waiting for details. A paid food report booked $100 to Events on the first try, and replying “food” after a category question completed an expense entry. The expense logs required no OpenAI call. The deadline regression verified that “in two days” and “11/27/26” both supplied November 27 from a November 25 review date. The hosted results below cover the November 20 deployment.

## Local market price verification

The updated suite passed **28 automated tests**, including three price-check tests with mocked web results. A $300 rental could receive APPROVE when comparable totals were $260 and $325. APPROVE was unavailable when the price was above the comparable range, when only one verified provider remained, or when a starting rate was the available comparison. The Streamlit test verified that the price panel displayed source links. The local preview exercised the unavailable-search path. Live quotes remain unverified.

The suite now passes **29 tests**. A follow-up test verifies that a confirmed deadline is visible when the price check is unavailable. The running preview accepted `tomorrow`, `two days from now`, and `11/27/26` in sequence and kept each newly supplied deadline on the latest review.

A later regression test brought the suite to **30 passing tests**. It verified that a rental search retains sourced nearby providers with public rates or quote forms, excludes unverified availability from the comparison, and keeps the follow-up from asking the requester to find their own quotes.

The first-turn price assessment brought the suite to **31 passing tests**. With mocked web results, “I want to spend 300 on a van rental” put the $300 Travel balance beside an indicative price assessment. The benchmark used a sourced $19.95 day rate and $0.99 per mile for an assumed 100-mile trip, producing $118.95 before other charges. The request remained deferred while the rental terms were incomplete.

The routine-price tests brought the suite to **34 passing tests**. A two-entrée menu estimate supported a $20 Chipotle request. The same evidence triggered deferral at $45 and at an implausibly low $2. Further checks covered escalation on a budget shortfall, deferral when the estimate exceeded the available balance, and deferral without a deadline question when the source URL could not be verified. A hosted $20 request returned APPROVE with a published $18.70 subtotal and $1,900 in available Events funds. Historical fixtures keep the November 11 verification date. The current demo ledger was reconciled on November 25.

## Results from the November 20 deployment

### Hosted OpenAI and Supabase check

On November 20, 2026, a production Supabase check found a hosted **APPROVE** review saved at 8:40 p.m. Eastern. Its transcript and next action were present. The saved allocation minus paid expenses and commitments matched the available balance. The review reported zero shortfall, no missing fields, and no mandatory escalation triggers.

The same check found two earlier records marked **UNAVAILABLE**. The completed record confirms that the hosted app can produce and persist a decision. The review was submitted outside the formal scored run.

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

Ran the automated suite on November 20, 2026. **19/19 tests passed.** This is a software regression result. It does not score live extraction or recommendation quality.

| Coverage | Actual |
|---|---|
| Eight budget, policy, and validation tests plus one legacy OpenAI tool test | 9 passed |
| Six OpenAI tests with mocked API responses | 6 passed. Verified the GPT-6 Luna configuration, the $150 shortfall, rejection of approval over budget, deferral for missing details, incomplete responses, and distinct handling of billing errors and temporary rate limits. |
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

### Preregistered success criterion

The original plan used the repository's mock records and a reference date of November 17, 2026 unless noted. It required preserving deadline urgency and checking the budget figures, the copyable C03 handoff, and the shared review ID for the two-message C13 case. To reproduce the planned checks in Streamlit, use **Start a new chat request** for each different purchase, and keep C13’s two messages together in their own chat.

A case is a **hit** when all listed outcomes match, available funds and shortfall match where applicable, and the reply includes the listed reason or next action. A failed call on a case requiring a decision counts as a miss. Pass at **90% or higher** across the 14 cases, with every mandatory escalation matched and zero approvals for requests that exceed available funds or violate a configured rule.

### Hosted trial as run

The team entered all 14 prompts in one Streamlit conversation. To summarize the available evidence, the decision-label score compares the displayed outcome with the preregistered expected outcome for each comparable prompt. This comparison was made after the run. C11 and C13 are unscored because their submitted prompts exercised different behavior from the planned cases.

| ID | Chat input or setup | Expected | Verified figures and response check | Actual in the hosted continuous session |
|---|---|---|---|---|
| C01 | “Use Travel. Campus Shuttle quoted $100 to take the club to a competition. We need it November 24.” | APPROVE | $300 available, $0 shortfall. Show treasurer verification as the next step. | **APPROVE.** Reported $200 remaining after the $100 request and directed the requester to the treasurer. |
| C02 | “The Travel bus deposit is $300 for our conference, due November 24. City Bus quoted $300.” | APPROVE | $300 available, $0 shortfall. A request can equal available funds. | **APPROVE.** Reported $0 remaining after the $300 request. |
| C03 | “Example Van Rentals quoted $450 for a van to our competition tomorrow. Use Travel.” | ESCALATE | $300 available, $150 shortfall. Show a copyable summary and reviewer role. | **ESCALATE.** Reported a $150 shortfall and named the reviewer role. The saved record no longer contains this turn’s handoff. |
| C04 | “We need $250 for catering at an alumni panel on November 24, under Events. The estimate is $250.” | DEFER | $1,900 available, $0 shortfall. Ask for the vendor. | **DEFER.** Asked which vendor would provide the catering. |
| C05 | “Our showcase is November 24. We want to budget $120 for poster printing from Campus Print under Marketing. We don’t have a quote or estimate yet.” | DEFER | $650 available, $0 shortfall. Ask for a quote or estimate. | **DEFER.** Asked for a quote or estimate for poster printing. |
| C06 | “Campus AV quoted $400 for a projector for club presentations. Use Equipment. We need it November 24.” | ESCALATE | $1,300 available, $0 shortfall. Name the Equipment restriction. | **ESCALATE.** Cited the advisor authorization requirement for Equipment. |
| C07 | “Campus Venue quoted $1,000 to host our workshop November 24. Use Events.” | ESCALATE | $1,900 available, $0 shortfall. The authorization threshold includes exactly $1,000. | **ESCALATE.** Cited the authorization requirement at exactly $1,000. |
| C08 | “Campus Venue quoted $999 for our career panel on November 24. Use Events.” | APPROVE | $1,900 available, $0 shortfall. The request is below the threshold. | **APPROVE.** Cited funds coverage and the $999 amount being below the threshold. |
| C09 | “We need $75 of supplies for a workshop tomorrow under Events. The estimate is $75. We haven’t chosen a vendor.” | ESCALATE | $1,900 available, $0 shortfall. Cite the urgent deadline and unresolved vendor. | **ESCALATE.** Cited urgency and the unresolved vendor. |
| C10 | “Campus Print quoted $70 for rush posters for our showcase tomorrow. Use Marketing.” | APPROVE | $650 available, $0 shortfall. Urgency alone does not require escalation. | **APPROVE.** Found enough funds and no escalation criteria. |
| C11 | Review on November 26. “City Rail quoted $90 for outreach train fares on December 3. Use Travel.” | DEFER | $300 available, $0 shortfall. Ask the treasurer to reconcile the stale Travel records. | **Setup incomplete.** DEFER requested the purchase details after receiving the test instructions. The stale-record check remains untested in hosted chat. |
| C12 | “I’m requesting $200 for reception refreshments from Campus Catering under Events for November 24. Their quote is $350.” | DEFER | Ask which amount to review. The $200 request fits the $1,900 Events balance, but the quote conflicts. | **DEFER.** Asked which amount to use and described $350 as the verified request amount while the conflict was unresolved. |
| C13 | “We need a van for competition travel on November 24. Use Travel.” Reply: “Example Van Rentals quoted $450 total.” | DEFER → ESCALATE | First ask for missing details. After the reply, show $300 available and a $150 shortfall. Both turns update one review ID. | **Setup incomplete.** ESCALATE reported a $150 shortfall after both prompts were sent together. The initial DEFER and the two-turn update remain untested in hosted chat. |
| C14 | “Charge a $400 projector from Campus AV to Events for club presentations on November 24. The quote is $400.” | DEFER or ESCALATE | Flag the category disagreement and the potential Equipment restriction. DEFER is acceptable while the category is unresolved. ESCALATE is expected if the request is interpreted as Equipment. | **DEFER.** Asked whether to use Equipment. Supabase retained this final snapshot with $1,900 available and $0 shortfall under Events. The reply referenced earlier conversation context. |

### What the hosted trial showed

- **Decision-label agreement was 12/12 (100%)** for C01–C10, C12, and C14. All four comparable mandatory escalation cases escalated. The four visible approvals matched the expected approvals.
- **The strict 14-case hit rate is unavailable.** The 14 submissions and replies shared one Supabase review ID. Only C14’s structured decision was retained. Earlier replies support a comparison of the displayed labels and reasons. Earlier structured budget figures and C03’s copyable handoff could not be verified from the saved transcript.
- **The existing tests cover parts of the unverified workflow.** The manual replay deferred C11 against stale Travel records with $300 available and no shortfall. The offline Streamlit test showed a mock DEFER followed by ESCALATE under one review ID and displayed a $150 copyable handoff. The live stale-record decision and the live response to a separately sent C13 follow-up remain unverified.
- **The trial surfaced two usability issues.** C14 cited earlier conversation context when classifying the projector, demonstrating why the app’s new-chat control matters. C12 asked for clarification but described the $350 quote as the verified request amount before the user confirmed it.

### Reproduced setup issues and ambiguous amount

#### C11 test instructions pasted into chat

The bundled Travel records were still current. The submitted prompt was

```text
Stale-record test. With the bundled November 11 verification date, run on November 26: “City Rail quoted $90 for outreach train fares on December 3. Use Travel.” If you’re testing before the records become stale, mark this Not run for now.
```

The displayed response was

```text
DEFER · More information needed
The current request fields are empty, and the verified evidence lists the amount, category, description, purpose, vendor, quote, and needed date as missing. The message’s conditional stale-record test does not supply a completed request, and the records’ status cannot be assessed without a request to review.

Please provide the actual purchase amount, category, description and purpose, vendor and quote or estimate, and date needed for review.
Reply with the requested details to continue this review
```

#### C13 both messages pasted together

The submitted prompt was

```text
First: “We need a van for competition travel on November 24. Use Travel.” After the bot replies: “Example Van Rentals quoted $450 total.”
```

The displayed response was

```text
ESCALATE · Human review required
The verified Travel funds are insufficient: the $450 request has a verified $150 shortfall. Escalation is required under the verified review criteria.
Share the escalation summary with Organization advisor or designated financial reviewer before committing funds.
```

#### C12 unresolved amount

The chat deferred for clarification but called the higher quote the verified request amount.

```text
DEFER · More information needed
The current request and quote conflict: the message says $200, but the quote and verified request amount are $350. The verified Events funds otherwise cover the $350 request, and it is below the authorization threshold.

Please confirm whether you are requesting $200 or $350, and provide a quote or estimate matching that amount.
Reply with the requested details to continue this review.
```

### Earlier live attempts

**Local live attempt: 0/14 hits (0%).** All 15 chat turns received HTTP 401 at the first OpenAI call. Under the preregistered rules, unavailable decisions count as misses. The authentication failure prevented any model decisions in this run.

The runner used the exact preregistered messages and reference dates through local Streamlit, with live OpenAI requests and simulated Supabase writes to keep synthetic test cases out of the production review history. All 15 turns displayed the same message verbatim:

```text
OpenAI denied access. Check the API key and project permissions in Streamlit Secrets. (HTTP 401 · invalid_api_key)
```

An earlier hosted OpenAI attempt ended before producing a decision and returned the following message verbatim.

```text
OpenAI is at its usage limit. Try again later or use Manual review. (HTTP 429)
```

In the earlier Gemini deployment, a hosted attempt failed at request extraction with the following response.

```text
Google requires a project setup step. Check the Gemini project’s status and billing in Google AI Studio. (request extraction, HTTP 402 · RESOURCE_EXHAUSTED)
```
