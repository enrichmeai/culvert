# Mainframe Segment Transform (Java)

This is a Java implementation of the `mainframe-segment-transform` Dataflow pipeline, designed for heavy loads where the JVM's performance and threading model provide advantages over Python.

## Overview

The pipeline:
1.  Loads a segment definition from a YAML template.
2.  Executes a SQL query against BigQuery (CDP tables).
3.  Formats each row into a fixed-width string.
4.  Writes sharded files to GCS.
5.  Generates a JSON manifest file for the downstream mainframe processes.
6.  Writes its terminal job-control status (`succeeded` / `failed`) for its `runId`.

## Job control

`fdp-trigger` inserts a `running` row into `job_control.pipeline_jobs` when it
launches this pipeline, and dedupes future triggers against it. This pipeline
closes that row out: `main()` blocks on `waitUntilFinish()` and then writes
`succeeded` on `DONE`, or `failed` on a thrown `Throwable` or any other terminal
state, through Culvert's `JobControlRepository` port -- never as raw BigQuery
DML. A non-terminal state (`RUNNING`, `STOPPED`, `UNKNOWN`, null) is refused
rather than recorded as a failure.

That write happens in the **Flex Template launcher process**, not on a Dataflow
worker. If the write fails, the launcher exits non-zero rather than reporting
success over a stale `running` row. If the launcher process is killed before the
job finishes, nothing records the outcome and the row stays `running` -- a known
gap that has to be corrected by hand.

Two options govern it:

| Option | Default | Notes |
|--------|---------|-------|
| `--jobControlTable` | `<gcpProjectId>.job_control.pipeline_jobs` | Fully-qualified `project.dataset.table`. **Must be the same table as fdp-trigger's `JOB_CONTROL_TABLE`** -- if the two disagree, the trigger's dedup gate never sees the completion and latches closed. |
| `--reportJobControlStatus` | `true` | Set `false` for local runs, which have no `job_control` row. |

A run with no `--runId` synthesises `manual-<millis>`, which has no
`job_control` row; the pipeline logs a WARN and skips the terminal write rather
than failing on a row that was never created.

> **Known gap (2026-09).** `fdp-trigger/src/fdp_trigger/launcher.py` sends
> snake_case Flex Template parameters (`run_id`, `extract_date`, `segment`,
> `extract_month`, `output_bucket`, `gcp_project`) while Beam derives flag names
> from the getters, so this pipeline only accepts camelCase (`--runId`,
> `--extractDate`, ...). It also never sends `templatePath`, which is
> `@Validation.Required`, and sends `segment` / `extract_month`, for which
> `SegmentOptions` has no property. A launch from the trigger therefore fails
> at option parsing before the pipeline starts. `MainframeSegmentPipelineTest`
> pins the camelCase contract; repairing the launcher is tracked separately.

## Comparison with Python Version

| Feature | Python | Java |
|---------|--------|------|
| Performance | Good for medium loads | Better for very large datasets |
| Startup Time | Faster | Slower (JVM overhead) |
| Type Safety | Dynamic (runtime) | Static (compile-time) |
| Logic | Matches exactly | Matches exactly |

## Configuration

Templates are compatible with the Python version. Both implementations use the same YAML structure for defining segments.

## Local Development

### Prerequisites
- Java 17 (the pom sets `<release>17</release>`)
- Maven 3.9+
- GCP Credentials

### Build and Test
```bash
mvn clean test
```

### Running Locally (DirectRunner)
```bash
mvn compile exec:java \
  -Dexec.mainClass=com.enrichmeai.culvert.deployments.segmenttransform.MainframeSegmentPipeline \
  -Dexec.args="--templatePath=../mainframe-segment-transform/config/templates/customer.yaml \
               --extractDate=20260514 \
               --periodStart=2026-05-01 \
               --periodEnd=2026-05-31 \
               --outputBucket=my-output-bucket \
               --reportJobControlStatus=false \
               --runner=DirectRunner"
```

## Deployment

Build and push the Flex Template using Cloud Build:
```bash
gcloud builds submit --config cloudbuild.yaml .
```
