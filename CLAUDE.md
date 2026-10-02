# Project rules for Claude / Copilot agents

## What this project is (read first — context is often lost between sessions)

- **Repo = `enrichmeai/culvert`** (renamed from `gcp-pipeline-reference` on 2026-05-30; the local folder is still `.../jsr/gcp-pipeline-reference/` until renamed between sessions). Builds **Culvert** — Java package `com.enrichmeai.culvert`, Maven modules under `data-pipeline-libraries-java/`.
- **Culvert replaced its retired predecessor.** The predecessor framework's code was removed from this repo in July 2026 (F1 legacy cleanup; it survives in git history) and its PyPI line is retired. Culvert is **released**: `culvert` on PyPI and `com.enrichmeai.culvert:*` on Maven Central (both 0.1.x), language-neutral contracts (`docs/CONTRACT.md`) + per-cloud adapter modules, proven end-to-end on a real GCP project. The **book** about Culvert lives in the private `enrichmeai/culvert-book` repo (it is a product to sell — never commit manuscript material here).
- **Strategy:** depth on GCP-Java first, then widen to multi-cloud (Joseph's "depth before breadth" call, 2026-05-27).
- **Where the truth lives:** `docs/framework-evolution/` (01–08) is the canonical plan. `06-sprint-plan-9-16.md` = current 8-sprint block; `08-groomed-backlog-9-16.md` = the ticket-level groomed backlog; `03-dev-process.md` = the full working agreement summarised below.

## Autonomous build loop (Joseph, 2026-09-26)

**Claude builds, the `reviewer` agent verifies, Joseph merges.** This is the same loop that
`valuedocs` runs, adapted to this repo. It is how **incremental work** moves here: one issue, one
branch off `main`, one PR into `main`. The sprint model below still applies when Joseph opens a
sprint. Outside a sprint, the loop is the default.

`/new-issue` (idea → ready issue) → `/groom` (Release board) → `/build-task <issue>` → hooks on every edit → `reviewer` → fix (max 3 attempts) → `/compound` → PR

**The four rules. They are not negotiable:**
1. **Verify before you write.** Any use of an external library, API, cloud service, CLI flag or
   config key (Beam, BigQuery, GCS, Pub/Sub, Secret Manager, Cloud Monitoring, Airflow, dbt,
   Testcontainers, Maven plugins, Terraform, GitHub Actions, the AWS and Azure SDKs, …) is checked against the
   official docs with WebFetch **before** you write the code, at the version the build resolves.
   Never guess a signature, flag or version. Start from § "Pinned docs" below. If they don't cover it,
   use the vendor's own docs, never a blog or Q&A site.
2. **Done means green.** A task is not done until the fast gates below pass locally, and the full
   suites pass in CI (cite the run). The header of `ci.yml` says the workflow is disabled at the
   GitHub level, and only Joseph can re-enable it. If CI did not run on the PR, run the module's whole
   suite locally instead (`mvn -pl <module> -am test` / the pytest recipe in the Dev-agent DoD below)
   and say in the PR that CI did not run. A gate that could not run is reported as not run, never as passing.
3. **Three attempts, then stop.** After 3 failed fix attempts at the same gate or reviewer finding,
   stop changing code and write the Blocker summary (format in `.claude/skills/build-task/SKILL.md` § 6)
   on the issue and in your reply.
4. **Pinned docs first.** Prefer the URLs in § "Pinned docs" over open-ended search. If you had to
   find a new one, add it there in the `/compound` step.

**Fast gates (exact commands):**

| Changed | Command |
|---|---|
| Java in reactor module `M` (`data-pipeline-libraries-java/*`, `deployments/*-java`, `deployments/reference-e2e-gcp`) | `mvn -B -q -pl <path to M> -am test-compile`, then `mvn -B -pl <path to M> -am test -Dtest='<the classes you touched>' -Dsurefire.failIfNoSpecifiedTests=false` |
| A reactor module added or removed | the `verify-module-list` job's check in `ci.yml` by hand: the `<module>` list in `data-pipeline-libraries-java/pom.xml` equals the list in `ci.yml` |
| Python package `P` under `data-pipeline-libraries/` or `python-culvert/` | `python3 -m venv /tmp/vw && /tmp/vw/bin/pip install -q -e "P[test]" && /tmp/vw/bin/python -m pytest P/tests -q`, plus `flake8 <files you touched>` |
| `.claude/hooks/**`, `.claude/settings.json` | `.claude/hooks/test-hooks.sh` (add a case for every new guard, and prove it RED first) |
| `*IT.java`, `mvn -P it verify` | needs Docker, so Joseph or CI runs it. Say it did not run |

**Hooks (`.claude/settings.json`, scripts in `.claude/hooks/`)** send errors straight back to you:
- **After each edit:** a syntax check and `flake8` for an edited Python file, and a syntax check for JSON
  and YAML files. Java is compiled once per turn instead, because that is too slow to do on every edit.
- **When the turn ends:** `test-compile` for every reactor module whose Java or `pom.xml` this
  branch touches, and the offline unit tests of every Python package listed in
  `.claude/hooks/fast-pytest.txt` that changed. The hook is skipped when nothing changed since the last
  clean run. It blocks the stop at most once. Opt out with `CLAUDE_SKIP_STOP_COMPILE=1`.
- **Before a Bash command:** `guard-destructive.sh` forces an approval prompt, even when an allow
  rule matches, for:
  - force pushes, any push to `main`, and ref/tag deletion;
  - **a commit whose message carries `[deploy]` or `[publish:deploy]`** (§ "Deploy & cost rules");
  - `mvn deploy`, the `release` profile, `mvn -P it verify`, `twine upload`, `hatch publish` and `gh release|workflow|secret`;
  - `gcloud`, `gsutil`, `bq`, `kubectl`, `helm install|upgrade|uninstall`, `terraform apply|destroy`, and the `scripts/gcp/` scripts;
  - `reset --hard`, `clean -f` and recursive `rm`.
  - `git commit -s` / `--signoff`: a DCO sign-off is a person's certification, never Claude's.

  The cases are pinned in `.claude/hooks/test-hooks.sh`.

**Agents and models.** `reviewer` and `groomer` run on **Sonnet** to save usage. Keep Opus for
design and debugging.

**Where things for Joseph go.** Anything that needs Joseph (a merge, a release, a key, a ruling, a GCP
run) goes on the PR or issue it belongs to. `/groom` lists it in the Joseph queue of the Release
board. That includes the **DCO sign-off** on Claude-authored commits: only a person can certify it
(`CONTRIBUTING.md` § "Sign your commits"), so the `DCO` check stays red until Joseph signs off or overrides it. **Never** post a secret or credential value anywhere on GitHub. Post only counts, SHAs and run IDs.

**One session per repo.** Only one Claude session works in this repo at a time, and it changes code
only in this repo. The GitHub Action builder (the `claude` label, `.github/workflows/claude.yml`) counts
as this repo's session. The book (`enrichmeai/culvert-book`, private) has its own session and
its own loop:
- **This repo is public. Never put manuscript text, chapter names or book issue links here.**
- A change here that alters a fact the book states (a contract count, an API name, a version, a
  release status) gets a `/new-issue` in `culvert-book`, opened from here. That repo is private, so
  a link to it is fine; the reverse is not.
- The book session reads this repo side by side. Locally, the folder is still
  `gcp-pipeline-reference/`, so the book session starts with `claude --add-dir ../gcp-pipeline-reference`.

**Releases are batched (Joseph, 2026-09-26).** Features merge into `main` one PR at a time, but a
release happens only once a chunk of features is done: the `wave:W1` set on the Release board. No PR
bumps a version, tags or publishes. Each PR adds its line under `## [Unreleased]` in `CHANGELOG.md`.
When every W1 item is closed, `/groom` proposes the release on the board, and Joseph decides. Then one
release PR sets the version and turns `[Unreleased]` into the version's section. **Merging it is the
release (Joseph, 2026-10-02):** `publish-pypi.yml` publishes to PyPI and then tags `vX.Y.Z` with a GitHub
Release, and `publish-maven.yml` uploads the signed bundle to Central's validation stage, where Joseph
presses Publish (`RELEASE.md` § "Automatic release"). Claude never tags or publishes by hand.

**Every release reaches the site (Joseph, 2026-09-26).** `enrichmeai.github.io/culvert/` shows the released
versions, every library, every pip extra and what each release added. Its `release-sync` workflow checks
the page against PyPI, Maven Central and this repo's `main` every day, and opens a `culvert-sync` issue there
when a release, a new library (a new reactor module) or a new extra leaves it behind. The site session fixes it
with `/release-sync culvert` (or you label that issue `claude`). So: give every release a `CHANGELOG.md` section (the site's "what's new" is written from
it), and give a new module a real `<description>` in its `pom.xml` (the site's library row is written from it).

**Usage discipline (Max plan).** One task per session. Pinned docs before search. The 3-attempt
cap. `/groom` is incremental after its first run.

### Pinned docs

Use the version the build resolves (`data-pipeline-libraries-java/pom.xml`, each module's
`pom.xml`, each package's `pyproject.toml`). Currently: Java 17 release target, Beam 2.55.0 (Java)
and 2.56.0 (Python), JUnit 5.10.2, Mockito 5.23.0, AssertJ 3.25.3, Testcontainers 1.19.8, Surefire
and Failsafe 3.2.5, Python ≥ 3.10, Airflow 2.9.x (Composer 2), dbt-bigquery ≥ 1.5.

Added 2026-09-26. Nothing below has been fetched from a session yet. The first session that fetches a row
marks it ✓ and deletes this note.

| Area | Doc |
|---|---|
| Apache Beam Java SDK 2.55.0 | https://beam.apache.org/releases/javadoc/2.55.0/ |
| Apache Beam Python SDK 2.56.0 | https://beam.apache.org/releases/pydoc/2.56.0/ |
| Beam programming guide | https://beam.apache.org/documentation/programming-guide/ |
| Dataflow | https://cloud.google.com/dataflow/docs |
| BigQuery Java client | https://cloud.google.com/java/docs/reference/google-cloud-bigquery/latest/overview |
| BigQuery Python client | https://cloud.google.com/python/docs/reference/bigquery/latest |
| GoogleSQL DML (`MERGE`) and quoted identifiers ✓ | https://raw.githubusercontent.com/google/zetasql/master/docs/data-manipulation-language.md · https://raw.githubusercontent.com/google/zetasql/master/docs/lexical.md. Fetched 2026-09-27 (#206) when `docs.cloud.google.com` was blocked by egress. Reading the pinned client SDK itself (`javap` on the 2.40.1 jar in `~/.m2`, the installed Python package source) is the fallback for API signatures |
| GCS Java / Python clients | https://cloud.google.com/java/docs/reference/google-cloud-storage/latest/overview · https://cloud.google.com/python/docs/reference/storage/latest |
| Pub/Sub Java / Python clients | https://cloud.google.com/java/docs/reference/google-cloud-pubsub/latest/overview · https://cloud.google.com/python/docs/reference/pubsub/latest |
| Secret Manager | https://cloud.google.com/secret-manager/docs |
| Cloud Monitoring | https://cloud.google.com/monitoring/docs |
| Airflow 2.9 | https://airflow.apache.org/docs/apache-airflow/2.9.3/ |
| Cloud Composer 2 | https://cloud.google.com/composer/docs/composer-2 |
| dbt (BigQuery adapter) | https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup |
| JUnit 5.10 | https://junit.org/junit5/docs/5.10.2/user-guide/ |
| Testcontainers Java | https://java.testcontainers.org/ |
| Maven Surefire / Failsafe 3.2.5 | https://maven.apache.org/surefire-archives/surefire-3.2.5/maven-surefire-plugin/ · https://maven.apache.org/surefire-archives/surefire-3.2.5/maven-failsafe-plugin/ |
| Maven Central publishing | https://central.sonatype.org/publish/publish-portal-maven/ |
| Python packaging (pyproject) | https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ |
| pytest | https://docs.pytest.org/en/stable/ |
| AWS SDK for Java 2.x | https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/home.html |
| Azure SDK for Java | https://learn.microsoft.com/en-us/azure/developer/java/sdk/ |
| Terraform google provider | https://registry.terraform.io/providers/hashicorp/google/latest/docs |
| GitHub Actions workflow syntax | https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions |
| claude-code-action | https://github.com/anthropics/claude-code-action |
| Claude Code hooks, subagents, permissions | https://code.claude.com/docs/en/hooks · https://code.claude.com/docs/en/sub-agents · https://code.claude.com/docs/en/permissions |

If WebFetch is blocked and the docs cannot be read, the "verify before you write" gate **did not
run**. Say so and treat it as a blocker. Never fall back to memory.

## How I want you to work (operating contract — enforce every session)

Multi-agent SDLC. Roles:
- **Engineer = Joseph** — direction, brand, the book, picks the next sprint, approves epics, merges/triggers releases.
- **Architect = the Opus session (you, by default)** — groom backlog into GitHub issues, dispatch, mediate standups, prep the sprint→main merge. Do NOT self-merge sprint→main; that's Joseph's trigger.
- **Dev-agents = Sonnet** (`Agent` tool) — one ticket each, ≤2h, post a DoD-checkbox comment per checkbox passed, open a PR into `sprint-N`, never self-merge.
- **Advisor = Opus** (`advisor()` tool) — review **every** dev-agent return + before declaring a sprint task done. The single advisor is the real throughput bottleneck **by design** — never let parallel returns degrade reviews into rubber-stamps.

Rules:
- **Every requirement becomes a GitHub issue before any code.** No mid-sprint scope expansion — open a new issue and slot it later.
- **In a sprint: branch off `sprint-N`; PR into `sprint-N`** (never main). `sprint-N → main` is one architect-authored merge commit at sprint close, on Joseph's go. **Outside a sprint** (the default since 2026-09-26): the § "Autonomous build loop" above — branch off `main`, PR into `main`, Joseph merges.
- **Team capacity: 4 dev-agents + 1 advisor per session; never dispatch >4 concurrently** (locked model — see `03-dev-process.md`). Cadence is 2h per *sprint* (wall-clock, up to 4 agents in parallel), NOT per ticket. Linear-dependency sprints under-utilise 4 — fine, don't manufacture false parallelism; worktree isolation when ≥2 agents touch the tree. This is convention — there is **no harness setting** that enforces it; the architect enforces it at dispatch.
- **Verify locally (CI is off during sprints; outside them, check whether `ci.yml` ran on the PR):** `mvn -o -pl <module> -am test` / `pytest`. Green unit tests ≠ prod-ready; `*IT.java` needs `mvn -P it verify` (Docker — architect/Joseph-run; dev-agents must NOT run it).
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
