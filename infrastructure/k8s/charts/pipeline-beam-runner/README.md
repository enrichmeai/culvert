# pipeline-beam-runner Helm Chart

A Helm chart for deploying Apache Flink via the Flink Kubernetes Operator. Use this for teams that cannot use Google Cloud Dataflow, or prefer Flink for beam pipelines.

## Prerequisites

The Flink Kubernetes Operator must be installed in the cluster before deploying this chart.

```bash
helm repo add flink-operator https://archive.apache.org/dist/flink/flink-kubernetes-operator-1.19.0/
helm install flink-operator flink-operator/flink-kubernetes-operator \
  --namespace flink-operator \
  --create-namespace
```

## Install

```bash
helm install pipeline-beam-runner ./pipeline-beam-runner \
  --namespace pipeline \
  --create-namespace \
  --set gcs.bucket=gs://my-bucket \
  --set serviceAccount.gcpSaEmail=pipeline-beam@my-project.iam.gserviceaccount.com
```

## Values

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `flink` | Flink base image |
| `image.tag` | `1.19` | Image tag |
| `jobManager.resources.memory` | `2048m` | JobManager memory |
| `jobManager.resources.cpu` | `1` | JobManager CPU |
| `taskManager.replicas` | `4` | Number of TaskManager replicas |
| `taskManager.resources.memory` | `4096m` | TaskManager memory per replica |
| `taskManager.numberOfTaskSlots` | `2` | Task slots per TaskManager |
| `gcs.bucket` | `` | GCS bucket for checkpoints (required) |
| `parallelism.default` | `8` | Default parallelism for jobs |
| `serviceAccount.gcpSaEmail` | `` | GCP service account for Workload Identity |

## Cleanup

```bash
helm uninstall pipeline-beam-runner -n pipeline
```

## Submitting a Beam pipeline

Once the chart is installed and the Flink session cluster is running, you can
submit Beam pipelines as `FlinkSessionJob` resources.  The chart ships two
example manifests and a helper script under `examples/` and `bin/`.

### 1. Build your Beam Java JAR

Package your Beam pipeline as a shaded (FAT) JAR so all dependencies are
bundled.  For a Maven project:

```bash
mvn package -DskipTests -Pflink-runner
# produces: target/customers-ingestion-1.0-shaded.jar
```

For the framework's reference deployment (`deployments/original-data-to-bigqueryload/`),
which currently targets Dataflow, re-target it at Flink by swapping the runner
import and dependency in `pyproject.toml` / `pom.xml`:

```
# Before (Dataflow)
--runner=DataflowRunner

# After (Flink)
--runner=FlinkRunner --flink_master=auto
```

See book Chapter 14 for a full discussion of the trade-offs between Dataflow
(managed, auto-scaling, per-byte pricing) and self-managed Flink (more
operational overhead, but full cluster control and no per-byte egress cost).

### 2. Build a Beam Python wheel (portable runner)

For Python pipelines using the Beam portable runner, package your pipeline as a
wheel and bake it into a Docker image:

```bash
# Build wheel
cd deployments/original-data-to-bigqueryload
pip wheel . -w dist/

# Build and push Docker image containing the wheel
docker build -t gcr.io/my-project/beam-python-pipeline:latest .
docker push gcr.io/my-project/beam-python-pipeline:latest
```

Pass `--environment_type=DOCKER --environment_config=gcr.io/my-project/beam-python-pipeline:latest`
when submitting.  See `examples/flinksessionjob-python-portable.yaml` for a
full annotated example.

### 3. Upload the artefact to GCS

```bash
gsutil cp target/customers-ingestion-1.0-shaded.jar \
  gs://pipeline-artifacts/beam-pipelines/customers-ingestion.jar
```

The TaskManager service account (set via `serviceAccount.gcpSaEmail` with
Workload Identity) must have `storage.objects.get` on that bucket.

### 4. Submit with `submit-beam-job.sh`

```bash
./bin/submit-beam-job.sh \
  --entity      customers \
  --extract-date 20260512 \
  --jar-uri     gs://pipeline-artifacts/beam-pipelines/customers-ingestion.jar
```

The script reads `examples/flinksessionjob-ingestion.yaml`, substitutes the
`${ENTITY}`, `${EXTRACT_DATE}`, and `${JAR_URI}` placeholders via `envsubst`,
then runs `kubectl apply -f` and polls until the job reaches `RUNNING` or
`FAILED`.

Pass `--namespace <ns>` if you installed the chart outside the default
`pipeline` namespace.

### 5. Verify the job

```bash
# List all session jobs in the namespace
kubectl get flinksessionjob -n pipeline

# Describe a specific job (shows events and status transitions)
kubectl describe flinksessionjob/pipeline-ingestion-customers-20260512 -n pipeline

# Stream logs from the TaskManager pods
kubectl logs -n pipeline -l component=taskmanager -f

# Open the Flink web UI
kubectl port-forward svc/pipeline-beam-runner-rest -n pipeline 8081:8081
# Then visit http://localhost:8081 in your browser.
```

### Example manifests

| File | Purpose |
|------|---------|
| `examples/flinksessionjob-ingestion.yaml` | Java Beam pipeline (recommended); uses envsubst placeholders for `submit-beam-job.sh` |
| `examples/flinksessionjob-python-portable.yaml` | Python Beam pipeline via the portable runner; requires a Docker image with your wheel pre-installed |
