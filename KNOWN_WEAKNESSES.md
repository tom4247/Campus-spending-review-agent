# Known weaknesses

**Version:** Chat-first reviewer using OpenAI GPT-6 Luna. Review recommendations are advisory. The treasurer or another authorized reviewer makes the final spending decision.

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
| **Chat depends on API access.** | OpenAI chat requires a funded API key. **Manual review** works without an API key. Live accuracy is still unmeasured. |
| **Checks depend on how the model interprets the request.** | Python enforces spending rules against the extracted amount and category. It cannot independently establish that the extraction is correct. Ambiguous dates, split costs, wrong categories, and corrections need live testing. |
| **Quote and vendor evidence is unverified.** | The model is instructed to ask about inconsistent quotes or categories. The chat path has no independent quote-total comparison, document verification, or vendor check. Treat these as model-dependent behaviors until the live cases are run. |
| **The explanation is generated.** | Structured validation checks the outcome and requires a reason and a follow-up for DEFER. It does not validate every wording or claim. Compare the rationale with the verified figures and policy checks. |
| **One purchase per conversation.** | Follow-ups reuse the same review ID and all previous turns. Start a new chat for a different purchase so the model does not mix details and update the earlier review. |
| **Each turn depends on two model calls.** | A slow or failed extraction or decision can leave the request unavailable. The app shows the error and offers Manual review. |
| **Chat text leaves the browser session.** | Chat sends the conversation to OpenAI and, when configured, saves it in Supabase. The public demo is intended for fictional data. |

## Budget, authorization, and workflow

| Weakness | What it means for the current version |
|---|---|
| **Budget accuracy depends on reconciliation.** | Missing and differently identified duplicate commitments distort the balance. A recent verification date alone does not establish that every obligation was reconciled. |
| **Demo records age.** | The bundled records were verified November 11, 2026. On November 26 they exceed the 14-day window. An otherwise routine request can then defer until the records are reconciled. |
| **One purchase, one category.** | The app does not allocate line items across categories or combine related requests. Separate requests can miss an authorization threshold that applies to their combined cost. |
| **Reviews do not reserve funds.** | Multiple requests can each appear affordable against the same ledger balance. For example, two $200 Travel requests each use the same $300 budget snapshot. |
| **Rules are illustrative.** | The configured restrictions do not capture a real club’s full policy. Deadlines are dates, so the agent cannot distinguish two requests due at different times on the same day. |
| **Malformed source records can block all reviews.** | CSV and policy files are loaded together. A duplicate ledger ID or malformed policy entry can stop the app before a request is reviewed. |
| **Escalation is a manual handoff.** | The copyable summary includes the relevant concern and reviewer role. It must still be sent by the requester. The app does not track receipt or the human’s final decision. |
| **History is session-scoped in Streamlit.** | Chat history is durable in Supabase, but the public UI lists only the current browser session’s reviews. It has no treasurer login, cross-session history view, or workflow for reopening an older request. Project administrators can inspect rows in Supabase. |
| **One latest snapshot per review.** | Follow-ups retain the text transcript and overwrite the latest structured decision and budget snapshot. The table does not retain a separate structured record for every revision. |
| **Database failures and incomplete sessions.** | A review can complete in the UI even if Supabase does not confirm the write. An interrupted request can leave a PENDING record after the first write. Manual submissions store inputs separately from chat reviews. |
| **Old results can still be visible.** | Earlier recommendations remain in the chat transcript. The latest result reflects the most recent submitted details and loaded records. |
| **APPROVE still requires authorization.** | A first-time user may read the label as permission to spend. The response displays treasurer verification and authorization as the next step. |
