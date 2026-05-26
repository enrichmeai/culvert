# Dev process for the Culvert framework

Sprint-0 artefact. This is the project-specific process layer. For the
general orchestrator / dev-agent / advisor / engineer role model, refer
to the canonical `DEV_PROCESS.md` maintained in the parallel
`enrichmeai/culvert-orchestration-notes` session (rule #72).

This file captures what's different about Culvert's process.

---

## Roles (project-specific reading)

| Role | Who | What they own here |
|---|---|---|
| **Engineer** | Joseph | Strategic direction, brand decisions (Culvert), the book, repo ownership. Approves epics. Picks the next sprint. |
| **Architect** | Claude (this session) | Sprint planning, issue refinement, dispatch order, advisor-mediated standups, merging. The "scrum master + lead dev" the engineer asked for. |
| **Advisor** | Stronger reviewer model (`advisor()` tool) | Standup classifier on agent return (on-track / needs-support / scope-broken / abort). Reviews each wave before the next dispatches. |
| **Dev-agents** | `Agent` tool sub-agents (sonnet by default) | Pick one ticket, work 2h max, post DoD-checkbox comments to the issue, close on done, abort with a comment if blocked. |

## Backlog discipline

**Every requirement becomes an issue before any code is written.** No
mid-sprint scope expansion. If something surfaces mid-sprint, the
architect (this session) opens a new issue under the relevant epic and
slots it into a future sprint — the running agent doesn't take it on.

Sprint-0's deliverable IS the backlog: see `04-sprint-plan.md`.

## CI is OFF during the sprint phase

GitHub Actions workflows are `disabled_manually` during Sprints 0-8 (see
issue #14) to save Actions minutes. **Verification is local only**:
`mvn -pl <module> -am clean test` for Java, `pytest <module>/tests/` for
Python. Dev-agents must not wait for CI signals on PRs — none will
arrive. Re-enable happens in Sprint 7 (book v1 ship) or after Sprint 8
— Joseph decides; see #14 and #17.

## Sprint cadence

| Sprint flavour | Length | Owner | Purpose |
|---|---|---|---|
| Human sprint | 2 weeks | Joseph | Outer cadence — feature themes, releases, the book. |
| Agent dev-sprint | 2 hours max | One dev-agent | One ticket from end to end. |

Multiple agent dev-sprints can run in parallel within a single human
sprint as long as their issues don't touch the same files.

## Oversized-ticket split rule

If an issue is estimated > 2h of agent work, the architect splits it
into 2-3 child issues BEFORE dispatch. Indicators of oversize:
- Three or more independent contracts / classes named in the DoD
- A "port the SQL from X" task that's > 200 lines
- Any "see also: <other module>" cross-cutting reference
- DoD checkboxes > 10

Issue #6 was the canonical example — bundled Warehouse +
JobControlRepository + FinOpsSink and got split into #6/#8/#9.

## Standup protocol (sub-agent runs are opaque-until-return)

The `Agent` tool doesn't expose mid-run state. Standups therefore
happen as **issue comments**, not orchestrator polling:

- **Dev-agent contract:** post a one-line comment on the issue every
  time a DoD checkbox passes. Example: `pom.xml replaced, mvn validate green`.
- **Architect between turns:** `gh issue view N --comments` to read
  progress on running agents before the next dispatch decision.
- **Advisor on agent return:** review the diff + the issue's comment
  thread, classify per agent (on-track / needs-support / scope-broken
  / abort).

A run that returns with zero comments and no commit is the strongest
"needs-support" signal — the architect re-dispatches with a tighter
brief or splits the ticket further.

## Stop-and-split rule (inside a sprint)

If a dev-agent realises mid-flight that the ticket is bigger than the
2h budget allows, the agent must:
1. Stop writing code.
2. Post a comment listing what's done vs left.
3. Return without closing the issue.

The architect then opens a follow-up issue rather than letting the
agent overrun.

## Mocking strategy (Java GCP modules)

**Mockito on Google Cloud client classes.** Not WireMock. The GCP Java
clients are gRPC, not REST — WireMock would be the wrong tool. WireMock
re-enters the picture in Sprint 6 (UAT scaffolding) for HTTP-style
adapters and internal demos only.

For sprint-1 GCP modules:
- `Mockito on com.google.cloud.bigquery.BigQuery` — the BQ adapters
- `Mockito on com.google.cloud.storage.Storage` — GCS
- `Mockito on SecretManagerServiceClient` — Secret Manager

Live-cloud integration tests are sprint-2+ scope.

## Sprint branch workflow (from Sprint 2 onward)

**Sprint 0** lands on `main` directly (process docs + scaffolding only).

**Sprint 1** also lands on `main` directly — issues #5-#9 were written
under the direct-to-main model and dispatching is imminent. Don't
rewrite them.

**Sprint 2 onward** uses a sprint branch:

```
main
  └── sprint-2 (cut from main at sprint start)
        ├── feature/issue-12-pubsub-source-sink     → PR into sprint-2
        ├── feature/issue-13-observability-hook     → PR into sprint-2
        └── feature/issue-14-dataflow-pipeline      → PR into sprint-2
                                                       │
                                                       ▼
                                              UAT against sprint-2
                                              (mvn test + pytest until
                                              Sprint 6, WireMock E2E
                                              from Sprint 6 onward)
                                                       │
                                                       ▼
                                              Single PR: sprint-2 → main
```

Concrete rules:

- **Architect cuts the sprint branch** right after the previous sprint
  merges. `git checkout -b sprint-N main && git push -u origin sprint-N`.
- **Dev-agents branch off the sprint branch**, not main. Branch name
  format: `feature/issue-<N>-<short-slug>`.
- **Dev-agents open a PR to the sprint branch**, not to main. PR body
  format: `Closes #<issue>`. The merge of the PR is the issue close —
  agents stop calling `gh issue close` directly from Sprint 2.
- **Parallel agents in the same module use `Agent` tool's
  `isolation: "worktree"`** so feature branches don't stomp each other
  on the local filesystem.
- **UAT runs against the integrated sprint branch** before the
  sprint→main merge. Until Sprint 6, UAT = `mvn -pl
  data-pipeline-libraries-java -am clean test` + relevant `pytest`
  invocations. From Sprint 6 onward it expands to WireMock E2E
  scenarios.
- **The sprint→main merge is a single PR** authored by the architect
  with a summary of the closed issues. No fast-forward — use a merge
  commit so the sprint boundary is visible in `git log --first-parent`.

This survives sprint-by-sprint and is captured as a backlog issue in
Sprint 0 (see `gh issue list --label process`).

## File-conflict rules

- **Parent POM** (`data-pipeline-libraries-java/pom.xml`): the
  architect edits this. Dev-agents never touch it. All sprint-1 module
  entries are pre-registered (see Sprint-0 commit).
- **`data-pipeline-core-java/`**: frozen for sprint-1. Contracts evolve
  only in dedicated tickets.
- **Module `pom.xml`** (the placeholders): the FIRST sprint-1 agent to
  pick up a module promotes the placeholder into the canonical
  `pom.xml` (deps, plugins). Follow-up agents in the same module add
  classes only, no `pom.xml` edits without a comment first.

## The "REPLACE THIS ENTIRE FILE" hint

Each sprint-1 placeholder `pom.xml` carries an explicit comment so the
implementing agent knows to rewrite rather than edit-in-place. Same
pattern recommended for any future scaffolding.

## Definition of Done (default for any ticket)

Unless the issue says otherwise:

- [ ] All DoD checkboxes in the issue body pass.
- [ ] `mvn -pl <module> -am clean test` (Java) or
      `pytest <module>/tests/` (Python) passes from repo root.
- [ ] Module `README.md` documents the public API.
- [ ] Commit message references `closes #N`.
- [ ] Issue closed with the commit SHA in the closing comment.

## 5-minute retro at sprint close

After every sprint closes (last issue merged / sprint→main PR landed),
the architect posts a **5-minute retro** as a comment on the sprint's
epic issue. Hard cap on time — this is not a write-up, it's a signal
for the next sprint.

Template (paste, fill, post):

```
## Retro — sprint-N (5 min)

**Shipped:** <closed issues with one-line outcome each>

**What worked:**
- <one bullet>
- <one bullet>

**What didn't:**
- <one bullet — be specific, name the issue / commit / agent run>

**Carry-over to sprint-(N+1):**
- <follow-up issue # if opened, or "none">

**One thing to change next sprint:**
- <one bullet — process tweak, not feature scope>
```

Rules:
- Architect writes it; engineer (Joseph) reads and reacts.
- Max five bullets across the whole retro. If you can't fit it in
  five, the sprint had too much scope — note that as the "one thing
  to change."
- The "one thing to change" must be actionable in the next sprint — no
  vague aspirations like "communicate better." Concrete tweaks only.
- Tag the comment with the `retro` label on the epic issue so retros
  are searchable across sprints.

## When to escalate to advisor mid-sprint

The architect calls `advisor()` (no params, full transcript forwarded):
- Before dispatching wave 1.
- On every agent return.
- When stuck — repeated failures, contradictory results, scope drift.
- Before declaring a sprint done.

Never call advisor for "is this approach OK?" if the architect can
verify directly with a tool call instead. Advisor is for genuine
judgment calls, not routine confirmation.
