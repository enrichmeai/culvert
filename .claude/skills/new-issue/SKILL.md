---
name: new-issue
description: Turn a rough idea, bug report or feature request into ready-to-build GitHub issue(s) in enrichmeai/culvert (or, for a fact the book states, enrichmeai/culvert-book), in the claude-task template's shape, de-duplicated, split to S/M size and labelled. Use for "new issue", "log this", "create a task/feature for …", "turn this into issues", or when Joseph describes work in a sentence.
---

# /new-issue — from a sentence to ready issue(s)

Same skill as in `valuedocs`, adapted to Culvert. The definition of **ready** is the `claude-task`
template (`.github/ISSUE_TEMPLATE/claude-task.md`): Goal · Measure · Evidence of done · Risk ·
Surface · Out of scope · Stop and ask if. `/groom` and `/build-task` both rely on it. Every issue this
skill writes fills every section, or says in that section why it cannot yet.

**This repo is public.** An issue here never quotes manuscript text, names a chapter, or links a
`culvert-book` issue.

## 1. De-duplicate first
Search open AND closed issues:
`gh issue list -R enrichmeai/culvert --search "<words> in:title,body" --state all --limit 20`.
Also check the canonical plan, where much of the backlog was groomed before issues existed:
`docs/framework-evolution/08-groomed-backlog-9-16.md` and `06-sprint-plan-9-16.md`.
- An open near-duplicate → add the new information as a comment there; do not create.
- A closed one → read why it closed. Fixed and regressed → new issue that links it. Declined by a
  ruling → tell Joseph, do not create.
- Already a ticket in `08-groomed-backlog` with no issue → create the issue from it and cite the ticket ID.

## 2. Place it
- Library code, contracts, adapters, deployments, CI, release tooling, docs → `enrichmeai/culvert`.
- A fact the **book** states that this change makes wrong → also a `/new-issue` in
  `enrichmeai/culvert-book` (private), linking this issue. The book lands after the code.

## 3. Size and split
- **S/M** (≤2 days, one concern; the DoD's ≤2h per dev-agent ticket still applies inside a sprint): one issue.
- **Bigger:** a parent issue (goal + ordered checklist) plus sub-issues. Each sub-issue is S/M,
  can be shipped and tested on its own, and is listed in build order.
- **A contract change** (`docs/CONTRACT.md`) is its own issue. It covers both languages (Java interface +
  Python Protocol), every implementer and every fake, because a half-changed contract breaks the
  conformance suites.
- **A new capability with open design questions:** write it up in `docs/framework-evolution/` first
  (the canonical plan), get Joseph's call, then come back here once per slice.

## 4. Write it (claude-task template)
- **Goal:** one sentence, the behaviour that will be true.
- **Measure:** the metric, and a baseline with the command that measured it (or why there is none).
- **Evidence of done:** name the red test that fails on main today, the green proof, and the re-measure.
- **Risk:** exactly one of docs / code / release / cloud.
- **Surface:** the modules or packages, found by grepping the code, not guessed.
- **Out of scope** and **Stop and ask if:** list every question you could not answer from
  the code, the docs or a ruling from Joseph. Never invent an answer to fill a section.

## 5. Label, never dispatch
Apply `wave:W1|W2|W3` (W1 only if the next release needs it, and say why in one line), an owner label
(`claude-ready` / `founder` / `mac-session`) and an `area:*` label. If a label is missing, create it
once with `gh label create` (colours: waves blue, owners green, areas grey). **Never** add the
`claude` label: it starts a paid build, and that is Joseph's call.

## 6. Draft or create
By default, show the drafts and wait for "go". If Joseph said "create" (or "just log it"), run
`gh issue create -R enrichmeai/culvert --title … --body-file … --label …`, with sub-issues linked to the
parent. Reply with the links, the wave and owner each issue got, and anything under "Stop and ask if".
