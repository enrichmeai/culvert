# Team Testing Plan

A written agreement about what is tested, by whom, with what tool, and when.
Referenced by the book's Chapter 13 ("End-to-End Testing, Tracing, and the
Developer Workflow").

A testing plan that lives in someone's head is not a testing plan — it is a
risk. This document is the one that lives in version control.

## Testing matrix

| # | Level                     | Who                 | Tool                                           | Frequency                 | Enforcement             |
|---|---------------------------|---------------------|------------------------------------------------|---------------------------|-------------------------|
| 1 | Static analysis           | Author              | `ruff`, `mypy`, `qodana`                       | Every save (pre-commit)   | IDE hint + pre-commit   |
| 2 | Unit tests                | Author              | `pytest`                                       | Every save, every push    | Pre-push + PR gate      |
| 3 | Structural DAG tests      | Author              | `pytest` + `DagBag`                            | Every push                | PR gate                 |
| 4 | Single-task tests         | Author              | `airflow tasks test`                           | Every push                | PR gate                 |
| 5 | Local SQLite DAG test     | Author              | `airflow dags test`                            | Every push (fast DAGs)    | PR gate                 |
| 6 | Local full-stack          | Author or reviewer  | `scripts/airflow-local/up.sh` (Docker Compose) | Before review of DAG work | Review held             |
| 7 | Real-GCP smoke (1 entity) | Reviewer            | `scripts/gcp/06_test_pipeline.sh`              | Before merge              | Merge blocked           |
| 8 | E2E full system           | CI                  | `scripts/gcp/e2e_pipeline_test.sh`             | Nightly + release tags    | Release blocked         |
| 9 | Load / chaos              | SRE                 | Custom + Locust + Gremlin                      | Quarterly                 | Capacity plan update    |
|10 | Security review           | AppSec              | Qodana + manual review                         | Each release              | Release blocked         |
|11 | Cost regression           | FinOps              | `finops_usage` SQL queries                     | Weekly                    | Alert to cost channel   |
|12 | Data-quality regression   | Data steward        | `data_quality_scores` dashboard                | Daily                     | Alert to data channel   |

## Roles

- **Author** — the engineer who wrote the code change.
- **Reviewer** — the engineer reviewing the PR, not the author.
- **CI** — the GitHub Actions workflows under `.github/workflows/`.
- **SRE** — the platform team responsible for capacity, reliability, and
  incident response.
- **AppSec** — the security team responsible for release sign-off.
- **FinOps** — the team or person responsible for cloud cost accountability.
- **Data steward** — the domain owner of a given entity's data.

Every testing level names a single owner. "Everyone" is not an owner. When a
test fails, the table tells you who is expected to act.

## Enforcement modes

Every level has a mechanical failure mode. No level is "just notice":

- **Pre-commit** — the hook fails; the commit does not land.
- **Pre-push** — the push fails; the developer fixes and retries.
- **PR gate** — the PR cannot merge while a required check is red.
- **Review held** — the PR sits in review until a human confirms the level
  ran green.
- **Merge blocked** — the merge button is disabled until the smoke run passes.
- **Release blocked** — the tag-driven release workflow refuses to publish.
- **Alert** — an alert is raised in the relevant Slack/PagerDuty channel.
- **Capacity plan update** — the quarterly capacity review incorporates
  the load-test findings.

## Cadence summary

| Frequency | Levels                                      |
|-----------|---------------------------------------------|
| Every save| 1                                           |
| Every push| 2, 3, 4, 5                                  |
| Before review / merge | 6, 7                            |
| Nightly   | 8                                           |
| Daily     | 12                                          |
| Weekly    | 11                                          |
| Quarterly | 9                                           |
| Per release | 10                                        |

## How to contribute to this plan

Changes to the plan are themselves reviewed like code. Propose a change by
editing this file, opening a PR, and tagging the platform team. Do not change
the matrix silently; everyone relies on it.

## Related

- `scripts/gcp/e2e_pipeline_test.sh` — the E2E harness.
- `scripts/airflow-local/` — the local full-stack harness.
- `scripts/dev/setup_sandbox.sh` — the per-developer sandbox workflow.
- `.github/workflows/` — CI enforcement.
- `docs/DEVELOPER_TESTING_GUIDE.md` — individual-level testing guidance.
