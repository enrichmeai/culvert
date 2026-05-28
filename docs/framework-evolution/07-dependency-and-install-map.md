# Dependency & install map — Sprints 9-16

**Purpose:** everything the autonomous run will install or depend on, so
Joseph can approve once up-front before automode. Probed against this
machine on 2026-05-27.

## Environment as probed

| Tool | Found | Notes |
|---|---|---|
| Java | 21 runtime (compile target release 17) | OK |
| Maven | 3.9.10 | OK |
| Docker CLI | 20.10.22 | installed |
| **Docker daemon** | **NOT running** | ⚠️ **Joseph action** — start Docker Desktop before Sprint 10 (Testcontainers needs it) |
| Python (default `python3`) | 3.14.3 | ⚠️ too new for Airflow |
| Python 3.11 | `/opt/homebrew/bin/python3.11` (3.11.14) | ✅ use this for Sprint 11 Airflow |
| Python 3.13 | `/opt/homebrew/bin/python3.13` | available, not used |
| GPG | 2.5.19 | OK for Sprint 16 release dry-run |

## Environmental prerequisites (Joseph action — one-time)

1. **Start Docker Desktop** before Sprint 10. All emulator integration
   tests (Sprints 10, 15) need a responsive Docker daemon. Without it,
   those sprints' ITs cannot run — the agent will detect this and stop
   rather than spin.
2. **Confirm Python 3.11 is the Airflow interpreter** for Sprint 11.
   Airflow does not support Python 3.14 (the default `python3`). The
   agent will create a `.venv_airflow` using `python3.11 -m venv`.

## Net-new dependencies by sprint

Everything Maven-side is **declared in module poms and downloaded
automatically** — no manual install. The only manual/heavy installs are
flagged **[INSTALL]**.

### Sprint 9 — Execution core
- **No new dependencies.** Uses Beam 2.55.0 (already pinned) + the
  Sprint-4 auto-config registry. Pure code.

### Sprint 10 — Emulator integration tests
- **Maven (auto-download):** `org.testcontainers:testcontainers`,
  `:junit-jupiter`, `:gcloud` — pin via a `testcontainers.version`
  property (latest stable, ~1.19.x). Test scope only.
- **[INSTALL] Docker images** (pulled automatically by Testcontainers at
  test runtime — needs Docker daemon + network):
  - `ghcr.io/goccy/bigquery-emulator:latest` (~50 MB)
  - `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators` for the
    Pub/Sub emulator (~1 GB — large; cached after first pull)
  - `fsouza/fake-gcs-server:latest` (~30 MB)
- No host package installs — Docker pulls handle it.

### Sprint 11 — Orchestration layer
- **[INSTALL] Python (Airflow):** `python3.11 -m venv .venv_airflow` then
  `pip install "apache-airflow==2.9.*" "apache-airflow-providers-google"`.
  Heavy (~250 MB with constraints file). Java side has **no new deps**
  (just model + renderer classes).
- Airflow install uses the official constraints file:
  `pip install "apache-airflow==2.9.3" --constraint
  "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.3/constraints-3.11.txt"`

### Sprint 12 — Observability depth
- **Maven (auto, BOM-managed):** `com.google.cloud:google-cloud-monitoring`,
  `com.google.cloud:google-cloud-logging` (both in libraries-bom 26.39.0
  — no version pin needed). OpenTelemetry already present from Sprint 2.

### Sprint 13 — FinOps depth
- **No new dependencies.** Uses the existing google-cloud-bigquery
  `JobStatistics` API.

### Sprint 14 — Data quality + error handling
- **No new dependencies.** Uses core contracts + existing adapters.

### Sprint 15 — CI re-enable + E2E
- **CI side:** GitHub Actions runners need Docker (for Testcontainers ITs)
  — GitHub-hosted ubuntu runners have it by default. No local install.
- Re-enables the 11 workflows disabled in Sprint 0 (issue #14).
- **Actions minutes resume here** — flagged for Joseph (this is the point
  cost resumes; see #14).

### Sprint 16 — Production hardening + release prep
- **GPG** (present, 2.5.19) for the `mvn -P release` signing dry-run.
  Needs a signing key in the keyring; if none exists the dry-run uses
  `-Dgpg.skip=true` and documents the gap rather than failing.
- **[NEEDS-ENGINEER] Dataflow perf test (T16.1):** real Dataflow jobs —
  Joseph runs, not the agent. Costs real money.

## Permission allowlist status

`.claude/settings.local.json` already allows: `mvn`, `gh`, `git`,
`python*`, `pip*`, `pytest`, `docker`, `docker-compose`, `curl`, `jq`,
`make`, archive tools, common file ops, `java`/`javac`/`jar`, `node`/`npm`.

**Gaps to add for this block:** `gpg`, `python3.11`/`pip3.11` venv paths
(`.venv_airflow`), and `gcloud` (in case an emulator needs the CLI). Added
in the same commit as this doc.

## Cost-resumption checkpoints (Joseph visibility)

| Sprint | Cost event |
|---|---|
| 10 | Docker image pulls (network egress, negligible $) |
| 15 | **GitHub Actions minutes resume** (#14) |
| 16 | **Real Dataflow perf test** — `needs-engineer`, Joseph-run |

Nothing in Sprints 9-16 spends GCP money autonomously. All adapter tests
run against emulators or mocks. The only real-cloud spend (T16.1) is
gated behind `needs-engineer`.

## Approval checklist

- [ ] Docker Desktop will be running for Sprints 10 + 15
- [ ] Python 3.11 approved as the Airflow interpreter (Sprint 11)
- [ ] `apache-airflow==2.9.3` install approved (Sprint 11)
- [ ] Emulator image pulls approved (BQ / Pub-Sub / fake-gcs)
- [ ] Actions minutes may resume at Sprint 15 (#14)
- [ ] Dataflow perf test (T16.1) understood as Joseph-run, not autonomous
