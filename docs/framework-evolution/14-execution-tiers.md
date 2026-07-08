# 14 — Execution tiers: local-first, then hybrid, then cloud

**Status:** principle (decided 2026-07). Describes the developer-experience
stance the framework is built around and the three execution tiers it already
supports. Not a work plan — the levers below exist in `main` today; this doc
names them so deployments, CI, and the deploy phase stay consistent with the
principle.

## The principle

**You should be able to run almost everything on your laptop.** A data-pipeline
framework earns adoption the way Spring did — by giving developers a fast inner
loop that needs no cloud account, no standing infrastructure, and no bill. Cloud
is where you *prove* and *ship*, not where you *develop*. Culvert is designed so
the same pipeline code runs unchanged across three tiers, and you climb the
tiers only as far as the task needs.

The seam that makes this possible is the contract set: the business logic
(`PipelineStage`/`IngestionRunner`/…) depends only on contracts, so *what a
`BlobStore` or `Warehouse` points at* — an emulator, a dev cloud project, or
production — is a wiring decision at the edge, never a code change.

## The three tiers

### Tier 1 — fully local (zero cloud, zero cost)

The fast inner loop. No cloud account required.

- **Data plane:** service emulators + LocalStack. GCS via the fake-GCS
  container, BigQuery via the emulator, Pub/Sub via the Pub/Sub emulator, and
  the AWS family (S3/DynamoDB/SQS/Secrets Manager) via LocalStack — all wired in
  `data-pipeline-it-support-java` and exercised by the `*IT` suites under
  `mvn -P it verify`.
- **Execution:** Beam's `DirectRunner` (`--runner=DirectRunner`, the launcher
  default) runs the pipeline in-process.
- **Orchestration:** local Airflow (docker-compose) parsing the same
  `deployments/data-pipeline-orchestrator/dags/culvert_dags.py` the cloud uses.
- **What it proves:** business logic, adapter behaviour against real API
  surfaces (emulated), DAG wiring, reconciliation, job-control transitions —
  e.g. `CrossCloudIngestionLocalStackIT` runs the *same* `IngestionRunner`
  against real S3 + DynamoDB (LocalStack) with no cloud spend.

### Tier 2 — hybrid injection (local execution → real dev cloud)

Same code, run locally, but the adapters point at a **real cloud dev project**.
This catches the things emulators can't: real IAM, real API quirks, real
network, real data shapes.

- **Data plane:** real GCS/BigQuery/Pub-Sub in a dev project (Application
  Default Credentials from `gcloud auth`), or the real AWS dev account.
- **Execution:** still `DirectRunner` — your laptop is the worker, the data is
  in the cloud. No Dataflow, no Composer, so no standing cost.
- **Orchestration:** local Airflow driving the DAGs against the dev-project data
  plane.
- **What it proves:** credential/permission wiring, adapter behaviour against
  the genuine service, and the config that Tier 3 will reuse — without paying
  for managed execution.

### Tier 3 — full cloud end-to-end (CI or local script)

The real thing, and the same invocation whether a human or CI runs it. Tier 3
has **two profiles**, and the demo profile is the default for the public repo.

#### Tier 3a — demo cloud (Cloud Run, scale-to-zero, ~£0) — DEFAULT

The profile the open-source demo env runs on. Proves the pipeline end-to-end on
**real GCP** without a standing bill.

- **Data plane:** a real GCP demo project — BigQuery/GCS/Pub-Sub within the
  always-free tier at demo volumes.
- **Execution:** **Cloud Run** runs the pipeline container (Beam `DirectRunner`
  inside the container — the worker is a Cloud Run task, not a managed Dataflow
  fleet). Cloud Run scales to zero, so between runs the cost is nothing; a demo
  run is a handful of vCPU-seconds within the free tier. This reuses the
  container/Cloud-Run pattern already in the repo (`fdp_trigger`,
  `google_cloud_run_v2_service` in `systems/generic`).
- **Orchestration:** **Composer is OFF by default** (`enable_composer = false`).
  The demo triggers runs via Cloud Scheduler → Cloud Run (the existing
  `fdp_trigger` seam) or local Airflow. No Composer environment is provisioned,
  so no standing orchestration cost.
- **What it proves:** the real GCP data plane, real IAM/credentials, and the
  full pipeline e2e — at demo scale, for ~£0.
- **Honest limit:** Cloud Run runs the pipeline as a container (single task /
  DirectRunner). It demonstrates correctness end-to-end; it is **not** the
  autoscaling, TB-scale path. That is Tier 3b.

#### Tier 3b — production cloud (Dataflow + Composer, metered)

The production execution path, exercised deliberately — not on every push.

- **Execution:** Cloud Dataflow (`--runner=DataflowRunner --region=…
  --stagingLocation=gs://…`) — managed, autoscaling Beam.
- **Orchestration:** Cloud Composer — validated **once** before publish to prove
  the `ComposerDagRenderer`/runtime on real Composer, then **torn down**
  (`enable_composer = true` only for that window; see
  [13 §2a](13-python-parity-release.md)).
- **What it proves:** the managed-runner path, autoscaling, real Composer, and
  the end-to-end SLA. Costs money, so it runs behind `/finops-estimate`.

**Both profiles share one driver.** A single script runs the whole thing,
invoked identically from a **local shell** or a **GitHub Actions** workflow
(keyless via Workload Identity Federation on the public repo). The profile is a
flag/var (`--runner` + `enable_composer`), not a different codepath — CI and
local runs must not diverge; the script is the source of truth and CI just calls
it.

> **Terraform note (2026-07).** The demo profile above is the target; the IaC is
> mid-consolidation. The modern `systems/generic` layer already has
> `var.enable_composer` (count-guarded) and the Cloud Run service pattern. The
> legacy flat `infrastructure/terraform/main.tf` still declares Composer
> **unconditionally** (`main.tf:408`) with a DAG-deploy `null_resource` — so an
> apply of that layer would incur Composer cost. Delivering Tier 3a means:
> (1) make `systems/generic` the canonical demo env and retire/guard the flat
> layer's Composer; (2) add a Cloud Run **pipeline-executor** resource (today's
> Cloud Run is only the `fdp_trigger`); (3) containerise the deployment (no
> `Dockerfile`/jib yet). Tracked as its own sprint.

## The levers (already in `main`)

The launcher (`IngestionMain`, and the same pattern in the other Java
deployments) exposes exactly the switches the tiers need:

- `--runner=DirectRunner|DataflowRunner` — Tier 1/2 and 3a (DirectRunner, incl.
  in the Cloud Run container) vs Tier 3b (managed Dataflow) execution.
- `--cloud=gcp|aws` — selects the adapter family (GCS/BigQuery/DynamoDB vs
  S3/Athena/DynamoDB); `azure` is rejected with the roadmap message.
- `var.enable_composer` (Terraform) — orchestration is Cloud Scheduler → Cloud
  Run when `false` (Tier 3a default, no standing cost), Cloud Composer when
  `true` (Tier 3b, the deliberate pre-publish validation window).
- Endpoint/credentials come from the environment (emulator env vars, ADC, or
  the CI-provided WIF identity) — so Tier 1→2→3 is a wiring change at the edge,
  never a code change.

## Why this is a headline, not an afterthought

1. **Adoption.** A contributor can clone, `mvn -P it verify`, and see the whole
   thing run green in minutes — no account, no card. That is the single biggest
   lever on open-source contribution.
2. **Cost.** Development happens at Tier 1 (free) and Tier 2 (near-free); Tier 3
   is reserved for proving and shipping. This is the same discipline the deploy
   phase encodes in [13 §2a](13-python-parity-release.md).
3. **CI/local parity.** Because Tier 3 is "run the script," there is no
   CI-only magic. What passes in CI is reproducible on a laptop and vice-versa.
4. **It's the book's argument, made concrete.** "The same pipeline, defined once
   against contracts" is not just cross-*cloud* — it's cross-*environment*. The
   tier model is where readers feel the payoff of the contract seam.
