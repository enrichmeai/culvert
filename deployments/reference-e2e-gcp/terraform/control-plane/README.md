# Control plane for the Phase 3 proof (#233)

This module provides the infrastructure that the real-GCP run of the proof (#234) needs.

| Part | What it is |
|---|---|
| **Cloud SQL** | PostgreSQL 16 on a private IP. It holds job control, stage claims and input readiness. |
| **Composer 2** | An environment whose workers reach the database. It runs the rendered DAG. |
| **Dataflow** | A service account for the Dataflow workers, with least-privilege IAM. |

**Applying it is the founder's step.** No apply runs from CI or a Claude session. What was checked
here is `terraform validate` and `terraform plan` against a placeholder project; see
[What was checked](#what-was-checked).

It is a child module of the deployment's root (`../`), off by default:

```hcl
# terraform.tfvars
control_plane = {
  enabled        = true
  project_number = "123456789012"
}
```

## What it creates

When enabled, it creates 24 resources. The root's own 7 resources are unchanged.

| | Resources |
|---|---|
| APIs | compute, servicenetworking, sqladmin, secretmanager, composer, dataflow. They are enabled, and left enabled on destroy. |
| Private IP | A reserved `/20` range and the service-networking peering that a private-IP Cloud SQL instance needs. Destroy abandons the peering rather than deleting it, because other services may share it. See [Teardown](#teardown). |
| Cloud SQL | A `POSTGRES_16` Enterprise instance (`db-custom-1-3840`, zonal, 10 GB SSD, autoresize). It has no public IP and only accepts encrypted connections. It also has the `culvert` database and the `culvert` user. Destroy abandons those two rather than dropping them, because Postgres will not drop a role that owns the schema's tables; deleting the instance removes them. |
| Database flags | `idle_in_transaction_session_timeout`, `tcp_keepalives_idle`, `_interval`, `_count` and `max_connections`. The next section explains them. |
| Password | Generated during the apply (an ephemeral `random_password`). It is written to the database user, then to a Secret Manager secret, through write-only arguments, so **it is never in the Terraform state or plan**. Bump `password_version` to rotate it. **If an apply fails after creating the user but before the secret version, bump `password_version` and apply again:** the password is new in every run, and only a version bump rewrites both. |
| Composer 2 | One environment on the same VPC, running as its own service account. It is told where the database is through `CULVERT_POSTGRES_HOST`, `_DB`, `_USER` and `_PASSWORD_SECRET`. It gets the secret's name, not the password. |
| Service accounts | `<prefix>-composer` has `composer.worker` and `dataflow.developer`, and may act as the Dataflow account only. `<prefix>-dataflow` has `dataflow.worker` and `objectAdmin` on the staging bucket. Neither has `cloudsql.client`: they reach the private IP directly and authenticate with the password. Add it only for the Cloud SQL Auth Proxy or a connector. Both may read the one password secret and no other secret. Composer's service agent gets `composer.ServiceAgentV2Ext`, which Composer 2 requires. |

## Why the session settings matter

- **A stage claim is a row lock held by an open transaction** (`PostgresStageClaim`). If the
  claimant dies, its session ends and the server releases the claim.
- **A claimant that hangs while still connected** keeps its claim until the server ends its session.
  `idle_in_transaction_session_timeout` is what ends it. The TCP keepalives end a session whose
  client vanished without closing the connection. Scenario 3 of the proof harness (#232) tests
  exactly this.
- **The timeout must be longer than the longest stage.** A stage keeps its transaction open, idle,
  while it works. A stage that outlives the timeout loses its claim, and its `complete()` fails, so
  the stage runs again on the next attempt. The default is 10 minutes (`claim_idle_timeout_ms =
  600000`). For the scenario 3 run itself, set it to a few seconds, or pass the harness
  `--session-timeout=server` to read it.
- **Connections are sized from `max_concurrent_stages`.** Each running stage holds one connection
  for its claim. It also opens short ones for job control, readiness and the Airflow gate check.
  `max_connections` is set to `max(100, 3 × max_concurrent_stages + 20)`, and Composer's
  `celery-worker_concurrency` to `max_concurrent_stages`.

## Inputs

These are the `control_plane` fields in the root. Unset fields take the module's default.

| Field | Default | What it is |
|---|---|---|
| `enabled` | `false` | Create the control plane. |
| `project_number` | *(required when enabled)* | The project's number, for Composer's service agent. |
| `network` | `default` | The existing VPC that Cloud SQL and Composer share. |
| `subnetwork` | `default` | The existing subnetwork, in `gcp_region`, for the Composer nodes. |
| `create_private_service_access` | `true` | Reserve a range and peer for private service access. Set it to `false` if the VPC already has one. |
| `sql_tier` | `db-custom-1-3840` | Cloud SQL machine type: 1 vCPU, 3.75 GB. |
| `claim_idle_timeout_ms` | `600000` | `idle_in_transaction_session_timeout`. Must be positive, and longer than the longest stage. |
| `max_concurrent_stages` | `4` | Stages that may run at once, 1 to 16. Sizes `max_connections` and the Composer workers' slots (`celery-worker_concurrency`). Past 16 the 0.5 vCPU worker would need to grow too. |
| `composer_image_version` | `composer-2.16.1-airflow-2.10.5` | The image `infrastructure/terraform/systems/generic` already pins. |
| `composer_worker_max_count` | `2` | Most Airflow workers. |
| `deletion_protection` | `false` | Protect the Cloud SQL instance from destroy. It is off so the proof tears down in one command. |
| `password_version` | `1` | Bump to generate and set a new database password. |
| `proof_task_seconds` | `2` | `CULVERT_PROOF_TASK_SECONDS` on Composer: how long each job-control call in the proof DAG sleeps, so the harness's scenario 6 can sample tasks running (#234). 0 to 60. |

The module also has these variables, which the root does not pass through, so they keep their
defaults:

| Variable | Default |
|---|---|
| `name_prefix` | `ref-e2e` |
| `private_service_prefix_length` | `20` |
| `sql_disk_gb` | `10` |
| `tcp_keepalives_idle` | `60` s |
| `tcp_keepalives_interval` | `10` s |
| `tcp_keepalives_count` | `6` |
| `composer_environment_size` | `ENVIRONMENT_SIZE_SMALL` |

It takes `project_id`, `region` and `staging_bucket` from the root's `gcp_project_id`, `gcp_region`
and `staging_bucket`.

## Cost

These are list prices from Google's pricing pages (cloud.google.com/sql/pricing and
cloud.google.com/composer/pricing), read on 2026-10-08. The Cloud SQL rates are the Enterprise
edition rates for MySQL and PostgreSQL. They are the rates the pages show by default, which I take
to be us-central1, the first region listed; I could not confirm which region the columns are for.
Other regions, such as the europe-west2 in the example settings, cost more or less. No discounts
are applied. Assume 730 hours a month.

| Item | Rate | Per month |
|---|---|---|
| Cloud SQL vCPU (1) | $0.0413 / vCPU-hour | $30.15 |
| Cloud SQL memory (3.75 GiB) | $0.007 / GiB-hour | $19.16 |
| Cloud SQL SSD (10 GiB) | $0.000232877 / GiB-hour | $1.70 |
| Composer 2 environment fee, Small | $0.35 / hour | $255.50 |
| Composer compute CPU (scheduler, web server, one worker: 1.5 vCPU) | $0.045 / vCPU-hour | $49.28 |
| Composer compute memory (6 GiB) | $0.005 / GiB-hour | $21.90 |
| Composer compute storage (3 GiB) | $0.0002 / GiB-hour | $0.44 |
| **Standing total** | | **about $378 a month (about $0.52 an hour)** |

**Not included:**
- Composer's per-environment database storage, which is a few cents.
- Composer scaling to a second worker. Each worker adds about $24 a month while it runs.
- The Dataflow jobs. They are billed per job, not as a standing cost.
- Secret Manager (cents) and network egress.

Composer is about 86% of the total. **Tear the stack down when the proof run is done.**

## Applying it (founder only)

```bash
cd deployments/reference-e2e-gcp/terraform
terraform init -backend-config="bucket=<your state bucket>"
terraform plan  -var-file=proof.tfvars -out=proof.plan
terraform apply proof.plan                  # about 25-40 min, mostly Composer
```

**Then, once:**
1. **Apply the schema.** The database has no public IP, so run this from a machine in the VPC (or
   through the Cloud SQL Auth Proxy with `--private-ip` on one). It is idempotent:

   ```bash
   SQL_IP=$(terraform output -json control_plane | jq -r .sql_private_ip)
   PGPASSWORD=$(gcloud secrets versions access latest --secret=ref-e2e-control-plane-db-password) \
     psql "host=$SQL_IP dbname=culvert user=culvert sslmode=require" \
       -f ../../../data-pipeline-libraries-java/data-pipeline-postgres-java/src/main/resources/com/enrichmeai/culvert/postgres/job_control.sql
   ```

   That file is the `job_control.sql` that `data-pipeline-postgres` ships. `ControlPlaneMain
   --apply-ddl` applies the same file, but it then runs the stages it is given, so use it only as
   the first step of a real run.
2. **Upload the DAG:** copy `dags/reference_e2e_control_plane.py` to the `composer_dag_gcs_prefix`
   output.

**Added for #234:**
- **The DAG's stores module reads these settings.** Given `CULVERT_POSTGRES_HOST`, `_DB`, `_USER`
  and `_PASSWORD_SECRET`, it reads the password from Secret Manager and connects with
  `sslmode=require`. The harness uploads it to the DAG folder next to the DAG.
- **The harness runs its Airflow scenarios on Composer** (`--composer-env`; see `proof/README.md`).
  The step-by-step run is `docs/CONTROL_PLANE_PROOF_GCP.md`.

**Still to add, outside #234's harness scope:**
- **The Dataflow stages.** They run as `dataflow_service_account` and need
  `CULVERT_POSTGRES_PASSWORD` from the secret at start. The proof's workers are `ControlPlaneMain`
  JVMs on a machine in the VPC, not Dataflow jobs.
- **IAM for the data the stages touch.** The Dataflow account can use only the staging bucket, and
  the Composer account none. Grant the buckets, topics and datasets the real stages read and
  write. If the DAG launches Java Dataflow jobs from the Composer workers, the Composer account also
  needs to write the staging bucket.

## Teardown

```bash
terraform destroy -var-file=proof.tfvars
```

This is one command because `deletion_protection` is off by default, with one risk not checked
here. The peering is abandoned, but its reserved range (`<prefix>-psa`) is still deleted, and GCP
may refuse to delete a range a peering still uses. If destroy stops there, finish by hand:

```bash
terraform state rm 'module.control_plane[0].google_compute_global_address.private_service_range[0]'
# later, once nothing uses the peering:
gcloud services vpc-peerings delete --service=servicenetworking.googleapis.com --network=<network>
gcloud compute addresses delete <prefix>-psa --global
```

With `create_private_service_access = false` (a network that already has private service access),
none of this applies.

- **Deleted:** the instance, its data, the secret, Composer, its GKE cluster and the service
  accounts.
- **Kept:** the APIs stay enabled, and the service-networking peering is abandoned, not deleted.
- **Composer's own bucket:** Composer creates a bucket for its DAGs and logs, which may remain
  after destroy. Delete it with `gcloud storage rm -r gs://<bucket>` (its name is in the
  `composer_dag_gcs_prefix` output).

## What was checked

- **Terraform 1.16.5**, with hashicorp/google 6.50.0 and hashicorp/random 3.9.1. The binaries were
  downloaded from releases.hashicorp.com and checked against their SHA256SUMS files. The GPG
  signatures on those files were not checked.
- **`terraform fmt -check`** and **`terraform validate`** pass.
- **`terraform plan`** was run against a placeholder project, with a local backend and
  `-refresh=false`, without credentials.
  - Control plane on: 31 to add, 0 to change, 0 to destroy. That is the root's 7 plus the module's
    24.
  - Control plane off: 7 to add, identical to the root on `main`.
  - The password shows only as `(write-only attribute)`.
- **The provider schema confirms** `password_wo`, `secret_data_wo`, the ephemeral
  `random_password`, `ssl_mode`, `deletion_policy`, `edition` and the Composer
  `workloads_config` blocks.
- **Not checked here:**
  - That Cloud SQL accepts these five flag names, and the default `max_connections` for this tier
    (the floor of 100 assumes the default is not higher). The Cloud SQL flags page was blocked by
    this environment's network policy, and `plan` does not check flag names; an apply rejects an
    unsupported one.
  - That `composer-2.16.1-airflow-2.10.5` is still offered. The Composer versions page was blocked
    too.
  - Anything that needs a real project: quotas, the org policies on the VPC, whether Composer's
    pods reach the private-service range without extra routes, a re-apply after a failed apply,
    destroy with the schema applied, and the apply itself.
- **No `.terraform.lock.hcl` is committed.** The registry was blocked, so the only hashes available
  were for linux_amd64, and a lock file with only those would fail `init` on other platforms.
  Commit the lock file from the first real `init`.
- **Airflow version:** the proof harness ran on Airflow 2.9.3 locally, while this image is 2.10.5.
  The rendered DAG uses only `PythonOperator` and `EmptyOperator`, but #234 should confirm it on
  2.10.
