# Culvert — Security IAM Reference

Covers: secret-logging audit (T16.2 §1), per-adapter least-privilege IAM roles (T16.2 §2).
CVE/dependency scan findings are in [`SECURITY_CVE.md`](SECURITY_CVE.md).

---

## 1. Secret-Logging Audit (T16.2 §1)

### Method

Grep corpus: all `.java` files under
`data-pipeline-libraries-java/` (13 modules, both `src/main` and `src/test`).

Queries run:

```bash
# 1. Log calls near secret/credential/token variable names in main sources
find data-pipeline-libraries-java -name "*.java" -not -path "*/test/*" \
  | xargs grep -n "\.debug\|\.info\|\.warn\|\.error\|\.trace\|System\.out\|printStackTrace"

# 2. Log method calls containing secret-adjacent keywords
find data-pipeline-libraries-java -name "*.java" \
  | xargs grep -n "log.*\(secret\|password\|credential\|token\|key\|payload\|data\)"

# 3. Proximity scan: log call within 8 lines of secret/credential keyword
# (awk sliding-window scan across all main source files)

# 4. Config/fixture scan: .properties, .yaml, .yml, .json for credential literals
find data-pipeline-libraries-java \
  -name "*.properties" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" \
  | xargs grep -l "password|secret|token|api.key|credential"

# 5. Hardcoded value scan in test fixtures
grep -rn '"s3cret\|"password\|"pass123\|"admin\|"secret123\|"apikey\|"api-key' \
  data-pipeline-libraries-java --include="*.java"

# 6. System.out / System.err / printStackTrace in main sources
find data-pipeline-libraries-java -name "*.java" -not -path "*/test/*" \
  | xargs grep -n "System\.out\|System\.err\|printStackTrace"
```

### Findings

**Production sources (`src/main`)**

| Module | Log caller | Finding |
|---|---|---|
| `gcp-secrets` | `SecretManagerProvider` | No logger declared; **zero log calls** in the class. The Javadoc explicitly states "Implementations never log the secret payload, even at DEBUG." The `get()` method returns the secret value directly without any logging. Clean. |
| `gcp-bigquery` | `BigQueryCostTracker`, `BigQueryAuditEventPublisher`, `BigQueryJobControlRepository`, `BigQueryWarehouse` | Log calls cover job IDs, `runId`, `BytesBilled`, `SlotMs` statistics — no credential/secret variables. Clean. |
| `gcp-gcs` | `GcsBlobStore`, `GcsCostTracker`, `QuarantineHandler` | Log calls cover URI paths, byte counts, and `runId`. No credential handling at log sites. Clean. |
| `gcp-pubsub` | `PubSubCostTracker` | Log calls on negative `messageCount` / `totalBytes` — operational counters only. Clean. |
| `gcp-observability` | `CloudMonitoringMetricsHook`, `CloudTraceObservabilityHook`, `DataCatalogLineageEmitter`, `CulvertMdcPopulator` | Monitoring hook logs pipeline/stage names and an `entryName`; trace hook relays user-supplied log level + message string; Data Catalog emitter logs `entryName` at DEBUG. No credentials at log sites. Clean. |
| `gcp-dataflow` | `DataflowPipeline`, `StageTransform` | No SLF4J logger declared; no `System.out`/`printStackTrace`. Clean. |
| `core` | `BudgetGovernancePolicy` | Uses `java.util.logging.Logger.warning()` for budget violation messages — includes policy name and cost, not any secret material. Clean. |

**No `System.out`, `System.err`, or `printStackTrace` calls exist in any production source file.**

**Test sources (`src/test`)**

Test fixtures contain synthetic placeholder values used to drive mock GCP Secret Manager
emulators (e.g. `"s3cret!"`, `"p@ss-1"`, `"ak-live-42"`, `"sign-xyz"`, `"tok-latest"`
in `SecretManagerProviderTest` and `SecretManagerProviderIT`). These are **not real
credentials**; they drive unit-test assertions against a fully mocked
`SecretManagerServiceClient`. No real API keys, service-account JSON, or
`.env` files are committed.

**No config files** (`.properties`, `.yaml`, `.yml`, `.json`) containing credential
literals were found under `data-pipeline-libraries-java/`.

### Observation — resource identifiers in `NotFoundException` message

`SecretManagerProvider.get()` throws:

```java
throw new NoSuchElementException(
    "Secret not found: projects/" + projectId + "/secrets/" + name
            + "/versions/" + version);
```

The exception message contains the **secret's resource identifier** (project, name, version)
but never its **value** (the payload returned by `accessSecretVersion`). Resource
identifiers are IAM-visible anyway (they appear in Cloud Audit Logs on every
`secretmanager.versions.access` call). The inline comment in the source already flags this
consideration: "Never include the secret name in a log; the message gives enough to debug."
The current implementation does not log this exception; callers that catch and log it would
expose the name, not the value. **No change required;** noted for caller awareness.

### Verdict

**Zero secret-value leaks found.** No code changes were made. The `mvn test`
skip is correct per the DoD ("if code changed") — no code was changed.

---

## 2. Least-Privilege IAM Roles per Adapter

All adapters use **Application Default Credentials (ADC)** — no service-account
keys in code. Assign roles to the service account bound to the Compute/Dataflow
worker (or the operator principal running the pipeline).

Use exact `roles/` IDs from `gcloud iam roles list` when writing Terraform or
`gcloud projects add-iam-policy-binding` commands.

### 2.1 `gcp-secrets` — Cloud Secret Manager

| Adapter class | API called | Minimum role | Why this role, not a broader one |
|---|---|---|---|
| `SecretManagerProvider` | `secretmanager.projects.secrets.versions.access` | `roles/secretmanager.secretAccessor` | Grants `accessSecretVersion` (read the payload). Does **not** grant `create`, `update`, `delete`, or `list`-payload on any secret version. The adapter never creates or destroys secrets, so neither `secretmanager.admin` nor `secretmanager.viewer` is correct. |

### 2.2 `gcp-bigquery` — BigQuery

| Adapter class | API / operation | Minimum role | Why |
|---|---|---|---|
| `BigQueryWarehouse` (query, load, insert) | `bigquery.jobs.create`, `bigquery.jobs.get`, `bigquery.tables.getData`, `bigquery.tables.updateData` | `roles/bigquery.jobUser` + `roles/bigquery.dataEditor` on the target dataset | `jobUser` lets the SA create and monitor jobs (required for any query or load). `dataEditor` allows row writes and table reads inside a specific dataset. Neither grants DDL on the dataset or any other project. Do **not** use `bigquery.admin`. |
| `BigQueryJobControlRepository` (job-control table reads/writes) | Same as above (table in same dataset) | Covered by `dataEditor` on the dataset containing the job-control table | No separate grant needed if the job-control table is co-located. |
| `BigQueryAuditEventPublisher` (insert audit rows) | `bigquery.tables.updateData` | Covered by `dataEditor` on the audit dataset | If the audit table is in a separate dataset, grant `dataEditor` there too. |
| `BigQueryCostTracker` (dry-run queries) | `bigquery.jobs.create` | Covered by `jobUser` | Dry-runs are billed as jobs; the SA must be able to create them. |

### 2.3 `gcp-gcs` — Cloud Storage

| Adapter class | API / operation | Minimum role | Why |
|---|---|---|---|
| `GcsBlobStore` (exists, get, put, openInput, openOutput, copy, delete, list) | `storage.objects.get`, `storage.objects.create`, `storage.objects.delete`, `storage.objects.list` | `roles/storage.objectAdmin` on the specific bucket | The adapter includes `put`, `delete`, and `copy` — objectViewer and objectCreator are too narrow. `objectAdmin` covers all object operations without granting bucket-level admin (create/delete buckets). Do **not** use `storage.admin`. |
| `QuarantineHandler` (write quarantine files) | `storage.objects.create` | Covered by `objectAdmin` on the quarantine bucket | If the quarantine bucket is separate, add `objectAdmin` (or `objectCreator` if no delete is needed) on that bucket too. |

### 2.4 `gcp-pubsub` — Cloud Pub/Sub

| Adapter class | API / operation | Minimum role | Why |
|---|---|---|---|
| `PubSubSink` / `PubSubCostTracker` (publish) | `pubsub.topics.publish` | `roles/pubsub.publisher` on the topic | Grants only `publish`. No subscription or admin rights. |
| `PubSubSource` / `PubSubCostTracker` (subscribe, acknowledge) | `pubsub.subscriptions.consume` | `roles/pubsub.subscriber` on the subscription | Grants pull + acknowledge. No publish or admin rights. |

Assign both roles if the same SA both produces and consumes.

### 2.5 `gcp-observability` — Cloud Monitoring, Cloud Trace, Data Catalog

| Adapter class | API / operation | Minimum role | Why |
|---|---|---|---|
| `CloudMonitoringMetricsHook` (`MetricServiceClient.createTimeSeries`) | `monitoring.timeSeries.create` | `roles/monitoring.metricWriter` | Grants only time-series write. Does not grant dashboard read or alert management. Do **not** use `monitoring.admin` or `monitoring.editor`. |
| `CloudTraceObservabilityHook` (OpenTelemetry → Cloud Trace exporter) | `cloudtrace.traces.patch` | `roles/cloudtrace.agent` | Grants trace-write only (patch spans). Does not grant read or admin. |
| `DataCatalogLineageEmitter` (`DataCatalogClient.createTag`) | `datacatalog.tags.create` (on entry) + use of tag template | `roles/datacatalog.tagEditor` on the entry's parent resource + `roles/datacatalog.tagTemplateUser` on the tag template | `tagEditor` grants create/update/delete of tags on catalog entries. `tagTemplateUser` is required to associate a tag with an existing template. Neither grants entry creation, schema edits, or admin. |

### 2.6 `gcp-dataflow` — Cloud Dataflow

Dataflow has two distinct principals: the **submitter** (the process that calls
`DataflowPipeline.runOnDataflow()`) and the **Dataflow worker service account** (the
VMs that execute the pipeline stages).

**Submitter principal**

| Operation | Minimum role |
|---|---|
| Submit and monitor Dataflow jobs | `roles/dataflow.developer` |
| Act as (impersonate) the worker SA | `roles/iam.serviceAccountUser` on the worker SA |

**Worker service account**

| Operation | Minimum role |
|---|---|
| Dataflow internal coordination | `roles/dataflow.worker` |
| Read/write GCS staging location | `roles/storage.objectAdmin` on the staging bucket |
| Data-plane roles (BigQuery, Pub/Sub, Secret Manager, etc.) | Same as §§ 2.1–2.5 above, depending on what the pipeline stages access |

Note: `DataflowPipeline.runOnDataflow()` accepts a `DataflowPipelineOptions` object
supplied by the caller. The Culvert adapter itself does not hardcode project, region,
or worker SA — those must be set by the operator in the `DataflowPipelineOptions`
before calling `runOnDataflow()`.

### 2.7 `core` — No GCP calls

`data-pipeline-core-java` contains no GCP API calls; it defines contracts and default
no-op implementations. No IAM roles required for the core module itself.

---

## 3. Notes on Role Binding Scope

- Prefer **resource-level bindings** (bucket, dataset, topic, subscription, secret) over project-level bindings.
- If a pipeline reads from one project and writes to another, grant the relevant roles in each project separately.
- The Dataflow worker SA is often different from the submitter; keep them separate and grant minimum permissions to each.
- Use **Workload Identity** in GKE rather than downloading service-account keys.

---

*Last updated: T16.2 (sprint-16, issue #106)*
