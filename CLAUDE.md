# Project rules for Claude / Copilot agents

## What this project is (read first — context is often lost between sessions)

- **Repo = `enrichmeai/culvert`** (renamed from `gcp-pipeline-reference` on 2026-05-30; the local folder is still `.../jsr/gcp-pipeline-reference/` until renamed between sessions). Builds **Culvert** — Java package `com.enrichmeai.culvert`, Maven modules under `data-pipeline-libraries-java/`.
- **Culvert REPLACES the existing published framework.** The PyPI `gcp-pipeline-framework` (Python, v1.0.29) is the **legacy** predecessor; Culvert is its successor — language-neutral contracts (`docs/CONTRACT.md`) + per-cloud adapter modules. It takes over the release line at the Sprint-16 "GCP v1.0.0 release prep" milestone. Implications: existing PyPI users will need a migration/deprecation path, and the Python modules must eventually reach parity (deferred to Sprints 17+) for the replacement to be real. The **book** documents the old framework; **book v2** (`docs/framework-evolution/05-book-v2-outline.md`) documents Culvert + this dev process.
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
