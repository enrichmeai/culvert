---
name: groom
description: Review and groom every open issue and PR in enrichmeai/culvert against the next release, and rewrite the Release board issue. Use for "groom", "what's pending", "what's left for the release", "what should I do next", at the start of a working day, or before picking the next task. Fans out to the Sonnet `groomer` agent; incremental after the first run.
---

# Grooming the Culvert backlog for the next release

Same skill as in `valuedocs`, adapted to Culvert. It reads and labels issues in this repo only and
never changes code. The book (`enrichmeai/culvert-book`) grooms its own board. This repo is public, so this board
never lists book work.

One pass answers three questions for Joseph: **what blocks the next release, what Claude can take
next without him, and what only he can do.** The output is one GitHub issue, the **Release
board** (title starts `Release board`, label `board`). It is rewritten on every run, so the answer
always lives in one place and survives every session.

## Rules
- **The release wave is the `wave:W1` label.** W1 = the next coordinated release (Maven Central +
  PyPI) cannot ship, or cannot be trusted, without it. The board's first line names that version,
  taken from the reactor `pom.xml` and `python-culvert/pyproject.toml`. If the two disagree, that is
  Drift. `W2` = the release after that, and `W3` = later.
- **Where the plan disagrees:** `docs/framework-evolution/06-sprint-plan-9-16.md` and
  `08-groomed-backlog-9-16.md` are the canonical plan (CLAUDE.md). When a label and the plan
  disagree, list it under Drift. Do not silently pick one.
- **Use the existing labels, not a new taxonomy:** `wave:W1|W2|W3`, `area:*`, and the owner labels
  `claude-ready` (Claude can build it unattended: tests prove it, no cloud, no Docker ITs),
  `founder` (Joseph: releases, keys, accounts, rulings, brand) and `mac-session` (needs a GCP project,
  Docker ITs, terraform or a publish). The first run creates any missing label with `gh label create`.
- **Safe writes happen; closures wait.** The run may add or remove the labels above and post a
  grooming comment. It never closes, merges or edits an issue body. Closures are
  proposed on the board as checkboxes, and Joseph ticks them. The NEXT run closes the ticked ones
  with `--reason "not planned"` or `completed` and a one-line comment naming the evidence.
- **Evidence or it did not happen.** "Already fixed" needs the merged PR or commit SHA.
  "Duplicate" needs the other issue number. "Obsolete" needs the ruling or the deleted code path.
- **Usage cap:** one groomer agent per ~25 items, and at most 10 agents per run. The first run grooms
  everything. Later runs groom only the items updated since the board's `last-groomed` stamp, plus
  every `wave:W1` item, plus anything with no wave label.

## 1. Snapshot (one call, compact)
```bash
S=${CLAUDE_SCRATCH:-/tmp}/groom; mkdir -p $S
gh issue list -R enrichmeai/culvert --state open --limit 500 \
  --json number,title,labels,updatedAt,author,body,comments \
  --jq '[.[] | {repo:"culvert", n:.number, title, labels:[.labels[].name], updated:.updatedAt,
         author:.author.login, body:(.body[0:1500]), ncomments:(.comments|length),
         last_comment:((.comments|last|.body // "")[0:600])}]' > $S/issues.json
gh pr list -R enrichmeai/culvert --state open --limit 100 \
  --json number,title,isDraft,updatedAt,headRefName,baseRefName,body,mergeable,statusCheckRollup,closingIssuesReferences \
  --jq '[.[] | {repo:"culvert", n:.number, title, draft:.isDraft, updated:.updatedAt,
         branch:.headRefName, base:.baseRefName, mergeable, closes:[.closingIssuesReferences[].number],
         checks:([.statusCheckRollup[]?.conclusion] | group_by(.) | map({(.[0] // "PENDING"):length}) | add),
         body:(.body[0:800])}]' > $S/prs.json
```
Read the current board (`gh issue list -R enrichmeai/culvert --label board --state open`) for its
`last-groomed` stamp and any ticked closure boxes. If there is no board yet, create it in step 5.

## 2. Close what Joseph ticked
For each ticked `- [x] close …` line on the board, re-check that the evidence still holds, then close the issue
(`gh issue close N -R enrichmeai/culvert --reason "<not planned|completed>" --comment "<evidence> — closed from the Release board"`).
If the evidence no longer holds, report it instead of closing.

## 3. Fan out to `groomer` (Sonnet)
Split the items into batches of ≤25. Launch the batches as parallel `groomer` agents. Give each one
the batch JSON, the repo path, the version W1 targets, and this rubric. Each returns one JSON row
per item (schema in `.claude/agents/groomer.md`).

## 4. Apply safe writes
- Apply the label changes the groomer proposed (`wave:*`, owner label) with `gh issue edit`.
- Post a grooming comment ONLY when the item is `wave:W1` and not ready: the proposed acceptance
  criteria, test approach and open questions, headed `Grooming (proposed — edit or reply to
  correct)`. Never post more than one grooming comment per item. Update your earlier one instead.

## 5. Rewrite the board
Body, in this order (keep it scannable on a phone):
1. `last-groomed: <UTC timestamp> · main <sha> · next release <version>`
2. **Release gate:** one line: N W1 items open (claude-ready X · founder Y · mac-session Z), and
   the critical path in dependency order (`A → B → C`).
3. **Joseph queue:** W1 items only he can do, each with the exact next action.
4. **Claude queue (next 5):** ready W1 `claude-ready` items in build order, each with its acceptance
   criteria link and size (S/M/L). These are what `/build-task` picks up.
5. **Needs grooming:** W1 items that are not ready, with the missing piece named.
6. **Proposed closures:** `- [ ] close #N — <duplicate of|fixed by|obsolete because> <evidence>`.
7. **Open PRs:** per PR: draft/ready, base (`main` or `sprint-N`), checks (or "CI did not run"),
   mergeable, stale (>24 h), and what it closes.
8. **Drift:** labels vs the canonical plan, pom vs pyproject versions, and a `CHANGELOG.md` entry
   missing for merged W1 work.
9. **Counts:** W2/W3/unlabelled counts only, not lists. Also the number of `## Compound` guards added since
   the last run (from merged PR bodies).

Create the board with `gh issue create -R enrichmeai/culvert --title "Release board (do not close)" --label board --body-file …`.
Update it with `gh issue edit <n> --body-file …`. Then reply to Joseph with sections 2–4 only.

## Optional: dispatch
`/groom dispatch N` also adds the `claude` label to the top N of the Claude queue. That starts
the GitHub Action builder on each one, one at a time (the workflow's concurrency group). Only do this
when Joseph explicitly asks: each dispatch spends Max usage.
