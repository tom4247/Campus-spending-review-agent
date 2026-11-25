# Known weaknesses

The hosted trial used the chat-first OpenAI deployment at `e90d812`, with GPT-6 Luna as the default. The payment reporting feature was tested locally. The treasurer or another authorized reviewer makes the final spending decision.

## Reproduced on the current manual reviewer

The following probes were rerun against the current Python review logic with the repository's mock data and a fixed review date of November 17, 2026. For the first four probes, start with a $200 Events refreshments request for a workshop on November 24, a named vendor, and a matching $200 quote. Change only the fields listed.

| Probe | How to reproduce | Observed result |
|---|---|---|
| Quote amount mismatch | Enter a $350 quote for the $200 request. | **APPROVE.** Manual review checks whether quote text is present. The [evaluation](AGENT_EVALUATION.md#current-failure-case-12) contains the full replay output. |
| Placeholder quote | Enter `TBD` as the quote. | **APPROVE.** Nonempty placeholder text satisfies the presence check. |
| Incorrect category | Describe a projector for club presentations and leave the category set to Events. | **APPROVE.** The Equipment restriction is applied to the selected category. |
| Placeholder vendor | Enter `Unknown` as the vendor. | **APPROVE.** The presence check has no vendor verification. |
| Duplicate commitment under a new ID | Review a complete $200 Travel shuttle request. In a copy of the ledger, duplicate the $900 hotel commitment under a different ID and review again. | The original **APPROVE** with $300 available became **ESCALATE** with −$600 available and an $800 shortfall. The unique ID check treats the two rows as separate obligations. |

For the first four probes, the reason was:

> Available funds are sufficient, required fields are complete, and configured checks pass.

## Chat models

| Weakness | What it means for the current version |
|---|---|
| **Chat depends on API access.** | An earlier hosted attempt returned HTTP 429. The app distinguishes credit and spend-limit errors from temporary rate limits when OpenAI supplies a diagnostic code or type. It retries once when a temporary error specifies a wait of up to three seconds. **Manual review** works without an API key. |
| **Hosted evidence is limited to a single conversation.** | 12 of 12 comparable decision labels matched. The [hosted trial](AGENT_EVALUATION.md#live-chat-test-set) verified the final structured review. The earlier budget snapshots, stale-record response, and two-turn response remain unverified in the hosted app. |
| **Checks depend on how the model interprets the request.** | Python enforces spending rules against the extracted amount and category. It cannot independently establish that the extraction is correct. Ambiguous dates, split costs, wrong categories, and corrections need live testing. |
| **User-supplied quotes and vendors still need verification.** | The public price check compares the requested amount with other provider prices. It cannot authenticate the vendor or the requester’s quote. In C12, chat asked the requester to resolve a $200 request and $350 quote while describing $350 as the verified request amount. |
| **A public benchmark can omit charges.** | Rental prices depend on dates, inventory, mileage, insurance, and fees. The agent shows source links and assumptions for its first-turn assessment. An all-in rental comparison requires equivalent terms and confirmed availability. |
| **The explanation is generated.** | Structured validation checks the outcome and requires a reason and a follow-up for DEFER. It does not validate every wording or claim. Compare the rationale with the verified figures and policy checks. |
| **Different purchases need to be separated explicitly.** | Follow-ups reuse the active review ID. In the hosted trial, 14 prompts shared one review ID, and the last reply cited earlier conversation context. Choose **Start a new chat request** when switching purchases. The running balance stays in the browser session. |
| **Purchase reviews depend on model calls.** | A slow or failed extraction or decision can leave the request unavailable. Proposed purchases with a known item and amount add a web-search request. A failed search prevents the chat from recommending approval on price grounds. |
| **Chat text leaves the browser session.** | Chat sends the conversation to OpenAI and, when configured, saves it in Supabase. The public demo is intended for fictional data. |

## Budget, authorization, and workflow

| Weakness | What it means for the current version |
|---|---|
| **Budget accuracy depends on reconciliation.** | Missing and differently identified duplicate commitments distort the balance. A recent verification date alone does not establish that every obligation was reconciled. |
| **Demo records age.** | The bundled records were verified November 11, 2026. On November 26 they exceed the 14-day window. An otherwise routine request can then defer until the records are reconciled. |
| **One purchase, one category.** | The app does not allocate line items across categories or combine related requests. Separate requests can miss an authorization threshold that applies to their combined cost. |
| **The running balance depends on reported payments.** | Several recommendations can rely on the same balance until the user records a payment. The app accepts one reported total per purchase review and has no receipt verification, installment tracking, or link to commitments already in the source ledger. |
| **Rules are illustrative.** | The configured restrictions do not capture a real club’s full policy. Deadlines are dates, so the agent cannot distinguish two requests due at different times on the same day. |
| **Malformed source records can block all reviews.** | CSV and policy files are loaded together. A duplicate ledger ID or malformed policy entry can stop the app before a request is reviewed. |
| **Escalation is a manual handoff.** | The copyable summary includes the relevant concern and reviewer role. It must still be sent by the requester. The app does not track receipt or the human’s final decision. |
| **History is session-scoped in Streamlit.** | A new browser session starts with the sample budget. The public demo has no treasurer login or cross-session budget view. When configured, Supabase retains review and payment records for project administrators. |
| **One latest snapshot per review.** | Follow-ups retain the text transcript and overwrite the latest structured decision and budget snapshot. The table does not retain a separate structured record for every revision. |
| **Database failures and incomplete sessions.** | A review can complete in the UI even if Supabase does not confirm the write. An interrupted request can leave a PENDING record after the first write. Manual submissions store inputs separately from chat reviews. |
| **Old results can still be visible.** | Earlier recommendations remain in the chat transcript. The latest result reflects the most recent submitted details and loaded records. |
| **APPROVE still requires authorization.** | A first-time user may read the label as permission to spend. The response displays treasurer verification and authorization as the next step. |
