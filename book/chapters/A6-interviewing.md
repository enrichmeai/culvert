# Appendix E — Interviewing for the Work

A framework is only as durable as the next engineer who joins the team. This appendix is the interview format I run when hiring senior data engineers onto a pipeline platform like the one in this book — internal moves and external hires alike. It is not a question bank to be read out verbatim. It is a structure designed to surface, in one hour, whether the person sitting opposite you can actually do the work the rest of the book describes.

I have settled on **six primary questions over sixty minutes, with a three-person panel and one candidate at a time**\index{interviewing}. The panel I prefer is the engineering lead (you, if you have built or operate the platform), the product owner who lives with the data, and a peer engineer from the team the candidate would join. Each person leads two questions; everyone takes notes; nobody dominates. Two candidates back-to-back in a morning is a comfortable cadence and lets the panel calibrate against itself while the conversations are still fresh.

## Why six questions in sixty minutes

Most engineering interviews fail in one of two directions. They either drown the candidate in trivia (name three Beam runners; what does `idempotency_key` do in `BigQueryIO.write`) or they ask one enormous question and run out of time before the answer goes anywhere interesting. Six questions is the sweet spot: enough breadth to cover ingestion, transformation, operations, security, and process; few enough that each conversation can actually breathe. Plan eight to ten minutes per question, leaving four minutes at the start for context and four at the end for the candidate's own questions.

The format below assumes a candidate who has worked on production data pipelines somewhere — not necessarily this stack, but something close enough that the vocabulary lands. If you are interviewing for a junior role, halve the depth and double the patience; the structure is wrong but the topics still cover the right ground.

## Suggested timing

| Block | Minutes | Lead |
|-------|---------|------|
| Welcome, context, role | 4 | Lead |
| Q1 — Ingestion design | 9 | Lead |
| Q2 — Remediation flow | 8 | Product owner |
| Q3 — Duplication: prevent and recover | 9 | Peer engineer |
| Q4 — dbt auth across environments | 7 | Lead |
| Q5 — Two-part data-quality scenario | 11 | Product owner |
| Q6 — CI/CD for data systems | 8 | Peer engineer |
| Candidate's questions | 4 | All |

If a question runs long because the answer is genuinely good, take time off Q6 — not off the candidate's own questions. That last block is where people decide whether to accept your offer.

## The six questions

The questions below are framed as prompts, what to listen for, where to push, and what counts as a red flag. The "what to listen for" sections describe *signals*, not vocabulary — score what the candidate understands, not which exact words they use. Two candidates can describe the same correct architecture in different terms; both should pass.

### Q1 — Design an ODP-to-FDP pipeline from a fixed-width file

> *Lead asks.* "You are landing a daily fixed-width extract — say, 200 GB, twelve million records, a header and trailer with control counts — into a GCS bucket. The business wants a clean BigQuery table downstream. Walk me through the architecture, from the moment the file lands to the point an analyst can query a curated view."

**Listening for.** A clean separation between the *envelope* (header/trailer record-count reconciliation\index{HDR/TRL}) and the *payload* (per-record parsing and validation). A landing-then-promote pattern, not direct-to-BigQuery writes. A bronze/silver/gold or ODP/FDP/CDP layering with a defensible reason for each layer. Schema-as-config rather than hand-rolled column lists. Reconciliation as a first-class step, not a footnote. A coherent story about where the work runs: Dataflow Flex Template for parsing because it scales, dbt-on-Composer (or equivalent) for the transformation, and a clear answer to "why those two and not one or the other".

**Push on.** What happens to records that fail validation — quarantine, dead-letter table, or hard fail the run? How is the run identified end to end, and how does that ID show up in the BigQuery rows themselves\index{run-id}? Where does the schema live — code, a SQL migration, a config file, a contract document? How would the design change if the file arrives in five parts with `.ok` sentinels instead of one\index{split files}?

**The no-golden-path follow-up.** Once the main answer lands, drop this in: *"What if there's no precedent for this — you are the first team to build a pipeline from this source, the source team has not produced a schema for you, and nobody internally has done one of these before. Where do you actually start?"* This is the senior signal you are testing for. You want to hear: ask the source team for a sample file and run statistics; profile it; propose a candidate schema; circulate it for review; build a small, throwaway pipeline against one day's data; only then commit to a long-term design. The opposite of "I'd look at the existing pipeline and copy it".

**Red flags.** Loading the raw file straight into the final BigQuery table. Treating validation as something to add later. No mention of reconciliation. Assuming the schema is fixed and known. Reaching immediately for Composer without considering whether the orchestration needs to be that heavy.

### Q2 — Walk a remediation cycle

> *Product owner asks.* "Yesterday's run finished. This morning we discovered three thousand rows in the foundation table have the wrong account-type code — a downstream business team noticed before we did. The data has already flowed into a consumable view. What do you do, in what order, with whom, on what timeline?"

**Listening for.** Calm, ordered thinking. Stakeholder communication first — "I tell the consumer-facing team we have a known issue and freeze the downstream view" — before any technical remediation. Then a triage step: how many rows, which entity, when did it start, is the source data wrong or did the transformation lie? Then a reversible fix: rerun the affected partition rather than patch values by hand. Then a verification step before unfreezing. Finally a post-incident note that ends up in a runbook, not a Slack thread.

**Push on.** Who owns the call about whether to roll back? What is the SLA promised to the downstream consumers, and does this incident breach it? How would the team know if the bug had been in production for six months instead of one day — and is that a different incident class? What guardrail would prevent the next instance?

**Red flags.** Reaching for `UPDATE` statements as the first option. No mention of the consumer-facing team until the technical fix is done. No clear distinction between "the data was wrong on arrival" and "we processed correct data incorrectly".

### Q3 — Prevent and recover from duplication in a dbt foundation model

> *Peer engineer asks.* "You own an FDP table — a foundation customer model — built with dbt-bigquery as an incremental model. Two-part question. First: how do you design it so duplicates cannot survive a partial rerun? Second: imagine duplicates have leaked in anyway — twenty thousand rows over a week. How do you recover, in production, without taking the table offline?"

**Listening for, part one.** `unique_key` declared on the incremental model\index{dbt!unique\_key}, with `incremental_strategy='merge'`\index{dbt!merge strategy}. An explicit understanding of *why* merge is right here and append is wrong. Awareness that `unique_key` is a model-level setting, not a column-level one, and that getting the natural key wrong is the most common cause of duplication in dbt. A passing reference to dbt tests — `unique`, `not_null` — as a CI guardrail. Optionally: window-function dedupe (`row_number() over (partition by key order by updated_at desc)`) inside the model itself as a belt-and-braces layer.

**Listening for, part two.** A reversible recovery path. Build a candidate clean table in a separate dataset, validate row counts and checksums against expected, then atomically swap (rename, or `create or replace table` from select). Keep the original table around until the swap has been verified for at least a day. *Never* delete from a foundation table directly: the cure causes the next incident. A note that the same recovery script should be parameterised by date range so the next time this happens it is a five-minute job, not a four-hour scramble.

**Push on.** What does the table look like during the swap — is there a window where downstream queries see an empty or partial result? How does the audit trail know that twenty thousand rows were retired rather than processed? Would you do this differently if the table were a Type 2 SCD rather than a current-state model?

**Red flags.** `DELETE FROM` as the recovery plan. No backup of the dirty table. No verification step before the swap. Confusion between `unique_key` and a BigQuery primary-key constraint (BigQuery does not enforce primary keys — `unique_key` is a dbt-level convention).

### Q4 — dbt authentication across environments

> *Lead asks.* "Your dbt project runs in three environments — a developer's laptop, a shared dev project in CI, and production. Authentication is different in each. How do you actually wire it up so the same dbt code works everywhere, with no service-account JSON keys downloaded to anyone's machine?"

**Listening for.** `profiles.yml`\index{profiles.yml} with three targets — `dev_local`, `dev_ci`, `prod` — selected by an environment variable. On the laptop, **user OAuth** via `gcloud auth application-default login`; in CI, the GitHub Actions runner authenticates via **Workload Identity Federation**\index{Workload Identity Federation}; in both non-laptop cases, the configured target uses `impersonate_service_account`\index{dbt!impersonate\_service\_account} to assume a dbt-specific service account, with the human or runner identity holding `roles/iam.serviceAccountTokenCreator` on that SA. The production SA has tightly scoped BigQuery permissions and nothing else. A clear statement that nobody — *nobody* — downloads a JSON key.

**Push on.** How does a new developer get set up on day one? What permissions do they need in the dev project — exactly? How is the production SA permissioned compared to the dev SA, and why is the difference what it is? How would the team know if someone tried to bypass impersonation and authenticated with a downloaded key instead?

**Red flags.** "We put the JSON key in a `.env` file." "We share one developer SA across the team." Treating impersonation as something dbt does opaquely rather than as an explicit `profiles.yml` setting. Not knowing the difference between `roles/iam.serviceAccountUser` and `roles/iam.serviceAccountTokenCreator`.

### Q5 — Validate a long-lived consumable data product

> *Product owner asks, then pauses for one part at a time.*
>
> **Part A.** "Imagine we have built a bespoke consumable data product for a business team — let's say a unified customer view aggregated from four foundation tables. It has been live in production for six months. Tens of millions of rows, growing daily. How would you validate the *quality* of the data in that product, on an ongoing basis, while it is in production?"
>
> **Part B.** "Now a separate but related question. The product owner has signed off the field mapping — every column in the CDP came from a specific source field somewhere upstream. How would you validate, in production, that the *mapping* is correct — that each field in the CDP genuinely is the right field from the source, not just a plausible-looking value?"

**Listening for, Part A.** Continuous data-quality checks rather than one-shot validation. Row-count reconciliation against expected upstream volumes, day over day. Schema drift detection: nullability, type, cardinality of categorical fields. Distribution checks: anomaly detection on key business metrics (mean, p50, p95, count of distinct customers per day) versus a rolling baseline. Referential checks against the upstream foundation tables. A dashboard the product owner can actually look at, not just a CI test that fires once a release. A clear treatment of *test data versus production data* — the senior answer recognises that quality in a six-month-old production product cannot be assessed from synthetic fixtures. **You are listening for the phrase "live data", or its equivalent.** A junior engineer reaches for unit tests; a senior engineer reaches for sampled production data with PII handled carefully.

**Listening for, Part B.** This is the harder half, and the one that separates strong candidates. Mapping validation is not the same as quality validation — it asks whether the *plumbing* is right. The senior answer is: take a statistically meaningful sample of records from the CDP, trace each mapped field back to its claimed source, and *compare the live value in the CDP against the live value in the source table for the same record*. Anything else — schema docs, contract files, code review — only proves the mapping was *declared* correctly, not that the data actually flows through it correctly. Watch for the candidate to volunteer this phrasing — *use live data, compare against the source* — without prompting. That is the senior signal worth hiring on.

**Push on.** How big is "a statistically meaningful sample" here, and why? What do you do when the source field has been transformed (formatting, currency conversion, code lookup) before it lands in the CDP — does the comparison need to invert the transformation? How would you keep this check running on a schedule rather than as a one-off audit?

**Red flags.** "We have a contract file; that documents the mapping." "We write unit tests with synthetic data." Confusing data quality (is the value plausible?) with mapping correctness (is the value actually from the right source?). Not naming live production data as the source of truth.

### Q6 — CI/CD for a data system

> *Peer engineer asks.* "Sketch the CI/CD pipeline for the system we have been talking about — without referring to any specific tool stack unless I ask. What stages does it have, what does each stage gate, and what is the deploy unit?"

**Listening for.** A clean stage progression: format and lint, unit tests, integration tests against an emulator or short-lived test project, build the deploy artefact (Docker image, dbt manifest, library wheel), deploy to a non-production environment, run a smoke test there, then promote to production behind a manual gate or canary. A clear notion of *what gets versioned* — semantic version on libraries, immutable image tags on services, environment-specific configuration kept out of the artefact itself. A separation between *publishing* (a library reaches an artefact registry) and *deploying* (a running system picks up a new version). Authentication via Workload Identity Federation, not stored keys.

**Push on.** What makes you choose trunk-based development versus GitFlow for this kind of system, and why? Where does the rollback live — is it a redeploy of the previous tag, a feature flag, a schema migration that has been written reversibly? How does the pipeline behave differently for a documentation change versus a library change versus an infrastructure change — are all three really running the same workflow, or do you path-filter them? What stops someone pushing directly to main and bypassing the gates?

**Red flags.** "We deploy on every commit to main." (No, you do not — or you do, and you have an incident every Friday.) No distinction between publishing and deploying. No mention of how secrets reach the runner. Treating CI/CD as a single workflow file rather than a layered set of gates.

## Calibration notes

A few things worth saying explicitly before the panel runs the morning.

**Score concepts, not vocabulary.** A candidate who says "we'd use a load-then-promote pattern" and a candidate who says "we'd stage the file in raw, then transform into a curated table" have given the same answer. Mark both up. The interview is not a spelling test.

**Numbers are ballpark, not exam-question.** If you ask how big a Dataflow worker pool needs to be for 200 GB and the candidate says "twenty workers for two hours, maybe ten if I tune shuffle", that is a fine answer even if the truth on your specific platform is fifteen for an hour. They are showing they have a model; the model can be calibrated on day one.

**Time-box ruthlessly.** If a question is going badly at the seven-minute mark, move on with a soft reset ("let me take us to the next one"). The interview's job is to surface enough signal for a hire/no-hire call, not to be exhaustively complete.

**One panel, one bar.** Before the candidates arrive, the three interviewers agree what a passing answer looks like for each question. After both candidates have been through, the three of you score in private, then compare. The most common failure mode of unstructured panels is interviewers drifting to different bars without realising; pre-agreed rubrics prevent that.

**Read for the senior signal in Q5 explicitly.** That is the question this format is really designed around. Q1 to Q4 and Q6 establish that the candidate can do the work; Q5 establishes whether they can do it *with judgement*. If a candidate answers Part B without ever volunteering "use live data", they are not a no-hire — but they need the follow-up, and the score reflects that they needed it.

## What good looks like

A strong candidate, summarised: walks the ODP/FDP design without reaching for buzzwords; treats validation and reconciliation as built-in stages, not bolt-ons; defaults to reversible operations on production data; names `impersonate_service_account` without prompting; volunteers live-data comparison for mapping checks; distinguishes publish from deploy; pushes back on at least one of the panel's assumptions politely.

A weak candidate gives the right answers in vocabulary but cannot explain *why* underneath. Probe with "what would go wrong if we did the opposite" — the gap shows up immediately.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Six questions, sixty minutes, three-person panel — enough breadth to cover ingestion, transformation, operations, security, data quality and process without rushing any single conversation.
  \item Q5 (the two-part long-lived-CDP scenario) is the senior-judgement question. The signal to listen for is the candidate volunteering \emph{live production data} as the source of truth for both quality and mapping checks.
  \item Score the concept, not the vocabulary. Two strong candidates can describe the same correct architecture in entirely different words.
  \item Calibrate before the candidates arrive: pre-agree the bar, pre-agree the rubric, pre-agree who leads what. Unstructured panels drift apart; structured panels converge.
  \item Reserve the last four minutes for the candidate's own questions, even when running over. Their questions are where they decide whether to accept your offer.
\end{itemize}
\end{takeaways}

\newpage
