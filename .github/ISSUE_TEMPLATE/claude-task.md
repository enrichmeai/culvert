---
name: Claude task
about: A task for the autonomous build loop (CLAUDE.md § "Autonomous build loop"). Creating it does not start anything. Review it, then add the `claude` label (Joseph's account only).
labels: []
---

## Goal

<!-- One sentence: the behaviour that will be true when this is done. -->

## Measure

<!-- Every task names its number, or says why it has none (test count, coverage, a latency, a cost line, a conformance row). -->
- Metric:
- Baseline, measured on main (command or run ID):
- Target:
- How it is read after merge:

## Evidence of done

<!-- Each line is checkable by someone who only reads the PR and its runs. -->
- [ ] Red proof: the test or guard that fails on main, quoted
- [ ] Green proof: the same test passing on the branch, quoted (the exact `mvn` / `pytest` command and counts)
- [ ] Both languages, when a contract changes: the Java and Python twins (`docs/CONTRACT.md`) and every implementer and fake
- [ ] Every doc that states a fact this changes, updated in the same PR (CLAUDE.md, Dev-agent DoD 5)

## Risk

<!-- Exactly one. It decides who runs what. -->
- [ ] docs: only *.md, not CLAUDE.md
- [ ] code: library or deployment code, tests
- [ ] release: versions, publishing config, anything that ships to Maven Central or PyPI (Joseph publishes)
- [ ] cloud: terraform, scripts/gcp, anything that touches a real GCP project (Joseph runs it, after /finops-estimate)

## Surface

<!-- Modules, packages or files expected to change. -->

## Out of scope

<!-- What must NOT change in this task. -->

## Stop and ask if

<!-- Conditions where Claude replies with a question instead of continuing. -->
- a test would have to be relaxed or a permission widened
- the change needs a GCP project, a deploy, a publish or a tag
- a public contract (`docs/CONTRACT.md`) would change shape
- the surface grows beyond what is listed above
