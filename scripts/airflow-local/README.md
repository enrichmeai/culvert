# Local Airflow Harness

A Docker Compose stack that runs the framework's Airflow DAGs against **fake
GCS, Pub/Sub, and BigQuery emulators**. No real GCP project required, no cost
incurred.

See the book's Chapter 12 ("Testing Strategy") for when to reach for this versus
the unit-test and single-task test modes.

## Stack

| Service            | Role                                    | Port  |
|--------------------|-----------------------------------------|-------|
| `postgres`         | Airflow metadata database               | —     |
| `airflow-init`     | One-shot DB migrate + admin user create | —     |
| `airflow-webserver`| Airflow UI                              | 8080  |
| `airflow-scheduler`| Airflow scheduler (LocalExecutor)       | —     |
| `gcs-fake`         | `fsouza/fake-gcs-server`                | 4443  |
| `pubsub-fake`      | `gcloud beta emulators pubsub`          | 8085  |
| `bq-fake`          | `goccy/bigquery-emulator`               | 9050  |

Airflow image: `apache/airflow:2.10.0-python3.11`.

## Quick start

```bash
# 1. bring the stack up
./scripts/airflow-local/up.sh

# 2. seed fixtures, buckets, topics, datasets
./scripts/airflow-local/seed-all.sh

# 3. trigger an ingestion run
./scripts/airflow-local/run-dag.sh ingestion_customers 2026-04-17

# 4. tear down (removes volumes)
./scripts/airflow-local/down.sh
```

UI credentials: `admin` / `admin`.

## How pipeline code reaches the emulators

The stack sets the standard Google emulator environment variables in the Airflow
containers:

- `STORAGE_EMULATOR_HOST=http://gcs-fake:4443`
- `PUBSUB_EMULATOR_HOST=pubsub-fake:8085`
- `BIGQUERY_EMULATOR_HOST=http://bq-fake:9050`

The framework's `data_pipeline_gcp_*` client wrappers (GCS, BigQuery, Pub/Sub
adapters) and the official Google client libraries pick these up automatically. No DAG-side code changes needed.

## What this does not do

- **Does not test Dataflow.** Dataflow has no local emulator. Tasks that submit
  to Dataflow will fail unless you stub them (see `data-pipeline-tester`).
- **Does not test Composer-specific behaviour.** For behaviour tied to Cloud
  Composer's Airflow build (for example private-IP networking), you need a
  real Composer environment or the sandbox flow under `scripts/dev/`.
- **Does not exercise Celery/Kubernetes executor.** Uses `LocalExecutor`.
  For executor-specific tests, see the self-managed Kubernetes charts under
  `infrastructure/k8s/charts/pipeline-system/`.

## Troubleshooting

- `docker compose logs airflow-webserver` — if the UI never becomes healthy.
- `docker compose logs airflow-scheduler` — if DAGs don't appear.
- `docker compose logs gcs-fake` — if uploads hang.
- Ports 8080 / 4443 / 8085 / 9050 already in use? Edit `docker-compose.yml`.

## Clean-room reset

```bash
./down.sh                     # drops volumes, wipes state
docker system prune -f        # only if you want to reclaim disk
./up.sh
./seed-all.sh
```
