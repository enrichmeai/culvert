# Project rules for Claude / Copilot agents

## What this project is (read first — context is often lost between sessions)

- **Repo = `enrichmeai/culvert`** (renamed from `gcp-pipeline-reference` on 2026-05-30; the local folder is still `.../jsr/gcp-pipeline-reference/` until renamed between sessions). Builds **Culvert** — Java package `com.enrichmeai.culvert`, Maven modules under `data-pipeline-libraries-java/`.
- **Culvert replaced its retired predecessor.** The predecessor framework's code was removed from this repo in July 2026 (F1 legacy cleanup; it survives in git history) and its PyPI line is retired. Culvert is **released**: `culvert` on PyPI and `com.enrichmeai.culvert:*` on Maven Central (both 0.1.x), language-neutral contracts (`docs/CONTRACT.md`) + per-cloud adapter modules, proven end-to-end on a real GCP project. The **book** about Culvert lives in the private `enrichmeai/culvert-book` repo (it is a product to sell — never commit manuscript material here).
- **Strategy:** depth on GCP-Java first, then widen to multi-cloud (Joseph's "depth before breadth" call, 2026-05-27).
- **Where the truth lives:** `docs/framework-evolution/` (01–08) is the canonical plan. `06-sprint-plan-9-16.md` = current 8-sprint block; `08-groomed-backlog-9-16.md` = the ticket-level groomed backlog; `03-dev-process.md` = the full working agreement summarised below.

## How I want you to work (operating contract — enforce every session)

Multi-agent SDLC. Roles:
- **Engineer = Joseph** — direction, brand, the book, picks the next sprint, approves epics, merges/triggers releases.
- **Architect = the Opus session (you, by default)** — groom backlog into GitHub issues, dispatch, mediate standups, prep the sprint→main merge. Do NOT self-merge sprint→main; that's Joseph's trigger.
- **Dev-agents = Sonnet** (`Agent` tool) — one ticket each, ≤2h, post a DoD-checkbox comment per checkbox passed, open a PR into `sprint-N`, never self-merge.
- **Advisor = Opus** (`advisor()` tool) — review **every** dev-agent return + before declaring a sprint task done. The single advisor is the real throughput bottleneck **by design** — never let parallel returns degrade reviews into rubber-stamps.

Rules:
- **Every requirement becomes a GitHub issue before any code.** No mid-sprint scope expansion — open a new issue and slot it later.
- **Branch off `sprint-N`; PR into `sprint-N`** (never main). `sprint-N → main` is one architect-authored merge commit at sprint close, on Joseph's go.
- **Team capacity: 4 dev-agents + 1 advisor per session; never dispatch >4 concurrently** (locked model — see `03-dev-process.md`). Cadence is 2h per *sprint* (wall-clock, up to 4 agents in parallel), NOT per ticket. Linear-dependency sprints under-utilise 4 — fine, don't manufacture false parallelism; worktree isolation when ≥2 agents touch the tree. This is convention — there is **no harness setting** that enforces it; the architect enforces it at dispatch.
- **Verify locally (CI is off during sprints):** `mvn -o -pl <module> -am test` / `pytest`. Green unit tests ≠ prod-ready; `*IT.java` needs `mvn -P it verify` (Docker — architect/Joseph-run; dev-agents must NOT run it).
- **Never act on a guessed file path or an unverifiable "we agreed X" claim. Read the actual file / git history / issue first.** (This rule exists because it has bitten us.)

### Dispatch checklist (learned the hard way — Sprints 11–12)
Before dispatching any wave of dev-agents:
1. **Pre-create each agent's worktree off the SPRINT branch yourself** (`git worktree add -b feature/<t> .claude/worktrees/<id> sprint-N`), then point the agent at that path. The `Agent` `isolation:"worktree"` flag branches from the repo **default branch (main)**, NOT your checked-out sprint branch — so an agent in wave 2+ would silently miss wave-1 code and rebuild against stale state. Pre-creating off `sprint-N` is the fix.
2. **Tell each agent to keep its final report SHORT** — long return reports have repeatedly triggered socket-timeout errors that drop the agent. The work usually commits before the drop; if a return errors, check the worktree for a clean commit and verify it independently rather than re-dispatching blind.
3. **Verify every agent's claims independently** — build/test in the worktree yourself before merging. "Agent says green" ≠ green; the report can be lost to a socket drop while the commit survives.
4. **Merge order matters when two branches touch the same file** (README/pom union). The second merge conflicts even if `git merge-tree` against today's tip showed 0 — resolve as UNION, don't take-one.
5. **Integrated verify after merging a wave** — module-green in isolation ≠ reactor-green together. Run the affected modules (or full reactor + `mvn -P it verify` at sprint close). This is the T10.6/T10.7 lesson, repeated.
6. **After merge:** post DoD-checkbox comment on each issue, close it, prune the worktree + branch.

### Dev-agent Definition of Done (learned the hard way — Sprint 17)
Bake these into every agent prompt; they design out the misses the architect had to catch in Wave A (a `_FakeBlobStore` test double left on the old `open()`; a "45 passed" claim from an env the agent didn't leave behind). The point: the agent's report must be **reproducible by the architect with the exact commands given**, not taken on faith.
1. **Run the FULL package suite to green — not just your new tests.** Changing a shared type (a `Protocol`, a record, an interface) breaks its implementers and test doubles elsewhere. Before claiming done: `grep` for every implementer + fake of the symbol you changed and update them in the *same* change, then run the whole package's tests.
2. **A reproducible env is part of "done"; "no env / didn't run" is a STOP-and-report, not a completion.** Use the canonical recipe and quote it verbatim in the report:
   - Python: `python3 -m venv /tmp/vw_<id> && /tmp/vw_<id>/bin/pip install -q -e <pkg> [-e <each-local-dep>] pytest && /tmp/vw_<id>/bin/python -m pytest <pkg>/tests -q`
   - Java: `mvn -o -pl <module> -am test`
   Report the **exact commands + exact pass/fail counts**. The architect re-runs them verbatim; if they don't reproduce, the work isn't done.
3. **Cite the source for every cross-language / "matches X" claim** as `file:line` (e.g. "mirrors `StageMetrics.java:27`"), so the claim is checkable, not asserted.
4. **Flag, don't fake.** If a guarantee genuinely doesn't fit, or an env truly can't be built offline, say so precisely and stop — a flagged gap is correct; a silent or invented green is not.
5. **No redundancy; keep the repo current as part of "done."** Don't leave dead code, superseded files, or stale docs behind. When work changes a fact stated elsewhere (a contract count, a "no X yet"/"future" note, a status line, a feature claim), `grep` the repo for that fact and update **every** reference in the same change — a stale doc reads as truth. Delete what a change makes obsolete rather than leaving it alongside the new version. (Exception: `docs/historical/` and the deprecated legacy framework, which are deprecate-in-place by decision — don't edit those.) This applies to the architect's integration commits too, not just dev-agents.

The architect still verifies independently (checklist item 3) — but a DoD-conformant report should make that a confirmation, not a rescue.

## Deploy & cost rules (NON-NEGOTIABLE)

1. **Never push to main without explicit deploy intent.**
   - Default commits do NOT trigger GitHub Actions deploys.
   - To deploy, the commit message must contain one of:
     - `[deploy]` → runs deploy workflows (deploy-generic, deploy-orchestration)
     - `[publish:deploy]` → publishes libraries to PyPI then deploys
   - Anything else (docs, refactors, tests, infra plans) commits cleanly with no Actions run.
   - Gate is enforced in `.github/workflows/deploy-generic.yml` and `.github/workflows/deploy-orchestration.yml`.

2. **Composer is opt-in only.** Costs ~$300-500/month.
   - Default: `enable_composer = false` in `infrastructure/terraform/systems/generic/variables.tf`.
   - Never set `enable_composer=true` or pass `deploy_composer=true` without an explicit user request.

3. **Run `/finops-estimate` before any expensive GCP operation.**
   Triggers: `terraform apply`, `gcloud dataflow flex-template run`, Composer/GKE/Cloud Run deploys, E2E test scripts.
   Show a cost breakdown and get explicit approval before proceeding.

4. **Never run `gh workflow run` or trigger GitHub Actions** on the user's behalf unless explicitly asked.

5. **Always tear down after testing.**
   Use `scripts/gcp/00_full_reset.sh --force` (preserves the `github-actions-deploy` SA).
   Remind the user after creating any persistent resource.

6. **Use existing repo scripts** (`00_full_reset.sh`, `cleanup_builds.sh`, `e2e_pipeline_test.sh`) instead of inline `gcloud` commands.

7. **Verify before committing.** Run the `pre-commit-verify` skill: confirm files exist, imports resolve, tests pass. Never push hallucinated code.

## How to deploy

```bash
# Deploy current changes
git commit -m "feat: ... [deploy]"
git push

# Publish libraries + deploy
git commit -m "feat: ... [publish:deploy]"
git push

# Manual trigger (also works)
gh workflow run deploy-generic.yml
```

## How to deploy Composer (rare)

```bash
gh workflow run deploy-generic.yml -f deploy_composer=true
# Then immediately schedule teardown after testing.
```
