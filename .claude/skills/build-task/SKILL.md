---
name: build-task
description: The autonomous build loop for ONE Culvert task — spec → verify docs → red test → implement (hooks check each edit) → reviewer agent → fix (max 3 attempts) → /compound → PR into main. Use for "build #N", "take the next task", "work on X", or when Joseph hands over a task to do unattended. With no argument, takes the top item of the Claude queue on the Release board.
---

# /build-task — one task, start to reviewed PR

Same loop as in `valuedocs`, adapted to Culvert. One task per session (Max usage limits: a fresh
session per task keeps the context small). If Joseph asks for a second task, finish or park this one first.

## 0. Pick and pin the spec
- With no argument, take the first item in the **Claude queue** on the Release board
  (`gh issue list -R enrichmeai/culvert --label board`). With an argument, take that issue.
- Write the spec down before anything else: the acceptance criteria (from the issue or its
  `Grooming` comment), the modules and packages it touches, and how a test proves each criterion.
  If anything is missing or ambiguous, comment the question on the issue, stop, and report. Do not guess scope.
- If this is a **contract change**, list every implementer and fake of the symbol in both languages now
  (`grep -rn "<Symbol>" data-pipeline-libraries data-pipeline-libraries-java deployments`). They
  all change in this PR (Dev-agent DoD 1).
- If it **needs cloud or Docker** (a GCP project, `mvn -P it verify`, terraform, a publish), build and
  unit-test what you can, then write the rest down as a Joseph action. Do not run it.

## 1. Set up
- `git fetch origin main`, then `git worktree add <scratchpad>/<topic> -b <branch> origin/main`.
  Branch off `origin/main`, never a stale local `main`. Inside a sprint, branch off `sprint-N` instead
  (CLAUDE.md § "How I want you to work").
- Claim the work before you build: a comment on the issue naming the branch, or the PR opened as a
  draft first. Read what open PRs already touch (`gh pr list`, `gh pr diff <n> --name-only`).

## 2. Verify before writing (CLAUDE.md § "Autonomous build loop")
For every library, API, cloud service, CLI flag or Maven plugin option the change will use, open its entry in
CLAUDE.md § "Pinned docs" with WebFetch, at the version the `pom.xml` / `pyproject.toml` resolves.
Note the URL you used, because the reviewer re-checks it. If it is not pinned, use the vendor's official docs only, then
add the URL to the pinned list in the `/compound` step. If the fetch is blocked, the gate did not run: say so.

## 3. Red, then green
Write the test that proves the first criterion, and show it failing for the right reason. Then
implement. The PostToolUse hook checks each edited Python/JSON/YAML/pom file and sends errors
straight back. The Stop hook compiles the touched reactor modules and runs the fast Python suites before
the turn ends. Fix what they report at once.

## 4. Gates — a task is not done until these pass
Run the fast gates for what changed (commands in CLAUDE.md § "Autonomous build loop") and quote the
exact command and the pass/fail counts, reproducibly (Dev-agent DoD 2). Then run the **whole** suite of
each touched module or package, not only your new tests (DoD 1). Push the branch, open the PR into
`main` as a **draft**, and read the CI run. If CI did not run (`ci.yml` is disabled at the GitHub
level), say so in the PR. Never claim a suite you have not seen green.

## 5. Review
Launch the `reviewer` agent with the spec from step 0. Fix every BLOCKER, every MAJOR and every
UNVERIFIED item. Answer each MINOR in one line (fixed / why not). Re-run the reviewer after fixing.

## 6. The 3-attempt cap
An **attempt** is one fix-and-recheck cycle against the same failing gate or the same reviewer
finding. After the 3rd failed attempt, stop changing code and post a **Blocker summary** on the
issue (and in your reply):
```
Blocked: <gate or finding>
Tried: 1. … 2. … 3. … (what each changed, what it showed)
Evidence: <error lines, doc URLs, run IDs>
Hypothesis: <best guess at the root cause>
Needs: <the decision, access or information that would unblock it>
```
Leave the branch pushed and the PR as a draft. Do not widen scope to route around the blocker.

## 7. Compound, then hand over
- Grep the repo for every fact this change alters (a contract count, a status line, a "not yet"
  note, a version, a README table) and update every reference in this PR (DoD 5). Add a `CHANGELOG.md`
  line under the unreleased section when the change is user-visible.
- If the change alters a fact the **book** states, open a `/new-issue` in `enrichmeai/culvert-book` and
  link this PR from there. Never link the book from here.
- Run the `/compound` skill. Then mark the PR ready and end with: branch, head SHA, files changed,
  gates run with their results, the reviewer verdict, the Compound lines, and anything for Joseph.
  **Joseph merges.** Never merge, tag or publish.
- **DCO** (`CONTRIBUTING.md` § "Sign your commits"): the `DCO` check needs a `Signed-off-by` matching
  each commit's author. A sign-off certifies the Developer Certificate of Origin, which only a person
  can do. Never add one for Claude, and never forge Joseph's. List it in the hand-over as a Joseph action:
  `git rebase --signoff origin/main` on the branch (then `git push --force-with-lease`), or the DCO app's
  override on the check page. (2026-09-26: #203 was the first PR to hit this.)
