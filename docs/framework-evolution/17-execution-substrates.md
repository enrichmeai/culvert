# 17 — Execution substrates: Composer 2 + pods, Composer 3, Cloud Run

**Status:** implemented (2026-09-03). The substrate a pipeline's tasks run on
is a **configuration choice, not a constant**. This document records the
research that shaped the design, the seam, and which substrates each deployment
supports.

## Why

Two consumers, two platforms, one pipeline:

| Landing zone | Orchestration | Cloud Run? | Role |
|---|---|---|---|
| **GCP 1.0 / CNE** | Composer 2, GKE pods | **No** | where the existing CDP pipelines run |
| **GCP 2.0** | Composer 3, Cloud Run | Yes | the demo target |

Before this, `deployments/data-pipeline-orchestrator/terraform/main.tf`
hardcoded `image_version = "composer-2-airflow-2"`, and the Cloud Scheduler →
Cloud Run alternative existed only as comments. The pipeline could not be
pointed at GCP 2.0 without editing it.

## The research, and how it changed the design

Verified against Google's docs before building, because it materially affects
the shape of the seam:

- [Composer 3 KubernetesPodOperator](https://docs.cloud.google.com/composer/docs/composer-3/use-kubernetes-pod-operator)
- [Composer versioning overview](https://docs.cloud.google.com/composer/docs/concepts/versioning/composer-versioning-overview)

**The expected finding was that Composer 3 breaks the pod pattern. It does
not.** `KubernetesPodOperator` is fully supported on Composer 3 and uses the
*same* `config_file="/home/airflow/composer_kube_config"` idiom as Composer 2.
What changes is the surrounding constraints:

| | Composer 2 | Composer 3 |
|---|---|---|
| GKE cluster | in **your** project, addressable | in the **tenant** project — *"it's not possible to configure it"* |
| Namespace | any you create | **always** `composer-user-workloads`, *"even if a different namespace is specified"* |
| Sidecars | multiple | **one**, only if named `airflow-xcom-sidecar` |
| Secrets/ConfigMaps | Kubernetes API | **not** via the K8s API — gcloud / Terraform / Composer API |
| Pod resources | arbitrary | predefined CPU/memory/storage values |
| Separate cluster | n/a | `GKEStartPodOperator` against a cluster unrelated to the environment |

Two corrections to the brief that prompted this work:

1. **"Composer 3 is GA with Airflow 3"** is imprecise. Composer 3 (branded
   *Managed Airflow Gen 3*) offers **both** Airflow 2 and Airflow 3, and
   Airflow 3 still carries documented gaps — upgrades via snapshots and
   in-place upgrades are *"not yet supported in Airflow 3"*. This deployment
   therefore pins the **Airflow 2** line as the conservative default.
2. **Evergreen versioning is a constraint, not just a convenience.** Gen 3
   environments take infrastructure updates automatically, so pinning an
   `image_version` is far less meaningful than it was on Composer 2.

**Design consequence:** Composer 2 + pods and Composer 3 are **one task pattern
under two constraint profiles**, not two patterns. Cloud Run jobs
(`CloudRunExecuteJobOperator`) genuinely are a different pattern. So the seam is
one renderer parameterised by a substrate policy, plus a distinct emission path
for Cloud Run — materially less work than two parallel pod patterns, and it
means GCP 1.0 and GCP 2.0 share one DAG body.

## The seam

**`ExecutionSubstrate`** (`data-pipeline-orchestration-java`) — an enum
carrying each substrate's constraint profile: Composer image family, pinned pod
namespace, whether a custom namespace is allowed, max sidecars, whether the
Kubernetes Secrets API is usable. `fromConfig(String)` accepts hyphens or
underscores in any case, so Terraform and Airflow config read naturally.

**`SubstrateDagRenderer`** — implements the existing `DagRenderer` interface and
emits `KubernetesPodOperator` or `CloudRunExecuteJobOperator` per substrate.

It **enforces** the constraints rather than documenting them. Composer 3
silently ignores a requested namespace and runs the pod in
`composer-user-workloads` anyway; a renderer that passed the namespace through
would emit a DAG that deploys cleanly, runs, and puts the workload somewhere
other than where its author asked — discoverable only in production. The
renderer refuses, and says why.

**Terraform** — `execution_substrate` selects the Composer image family
(`composer-2-airflow-2` / `composer-3-airflow-2`), decides whether
`node_config` is emitted at all (a Composer 2 concept; Composer 3 has no
user-owned cluster to configure), and gates the Cloud Run job resource.

`cloud_run_available` **fails the plan closed** on GCP 1.0 / CNE. This is a
`lifecycle` **precondition**, not a top-level `check` block, and deliberately
so: `check` assertions are advisory and only emit a *warning*, so a plan would
succeed and the deployment would go out targeting a substrate the landing zone
cannot run. The precondition hangs off the orchestrator service account because
that resource exists for every substrate — putting it on the Cloud Run job
would never fire, since that resource has `count = 0` in exactly the case being
guarded.

## Which substrates each deployment supports

| Deployment | Composer 2 + pods | Composer 3 | Cloud Run jobs | Notes |
|---|---|---|---|---|
| `data-pipeline-orchestrator` | ✅ | ✅ | ✅ (GCP 2.0 only) | The substrate is selected here; the others are triggered by its DAGs |
| `original-data-to-bigqueryload-java` | ✅ | ✅ | ✅ | Beam job; substrate decides how the launcher is invoked, not the pipeline |
| `postgres-cdc-streaming-java` | ✅ | ✅ | ⚠️ | Long-running streaming job — Cloud Run jobs are not a good fit for an unbounded stream |
| `mainframe-segment-transform-java` | ✅ | ✅ | ✅ | Batch, bounded |
| `bigquery-to-mapped-product` (dbt) | ✅ | ✅ | ✅ | dbt runner is a short batch container |
| `fdp-to-consumable-product` (dbt) | ✅ | ✅ | ✅ | as above |
| `reference-e2e-gcp` | ✅ | ✅ | ✅ | DirectRunner in tests; substrate applies to the cloud path only |

## Verified

- `SubstrateDagRendererTest` — 11 tests: each substrate renders the same
  `DagSpec`; Composer 3 pins the namespace and rejects a custom one; sidecar cap
  enforced; Cloud Run emits its own operator; config parsing.
- `terraform validate` clean; substrate → image-family mapping and the
  fail-closed precondition exercised for all three substrates plus an invalid
  value (the precondition exits non-zero; the `check` block it replaced only
  warned).

## Not done

The DAG files currently checked in at
`deployments/data-pipeline-orchestrator/dags/` are not yet generated through
`SubstrateDagRenderer` — the renderer and the Terraform selector are in place
and tested, but wiring the committed DAGs to be generated from a `DagSpec` at
build time is a separate change. Until then, selecting a substrate configures
the infrastructure correctly and the renderer produces the right DAG, but the
hand-written DAGs in that folder still need to be regenerated to match.
