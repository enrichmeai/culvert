# original-data-to-bigqueryload (Java / Culvert)

GCS → BigQuery ingestion on Culvert — the Java Dataflow conversion of the
predecessor Python-Beam deployment (T20.5, #140). Reads an HDR/TRL-enveloped
CSV from object storage, validates rows against the entity schema, loads valid
rows to the ODP table, quarantines invalid rows to the error bucket, reconciles
the envelope count against the loaded count, and records job-control status.

## Shape

- `envelope/` — HDR/TRL envelope parser (`EnvelopeParser`, header/trailer records).
- `CsvRowParser` — CSV rows → field maps.
- `IngestionRunner` / `IngestionPipelines` — the ingest flow: parse → validate
  (`DataQualityTransform`) → load (`Warehouse`) → quarantine (`BlobStore`) →
  reconcile → job-control updates (`JobControlRepository`).
- `stages/IngestionStage` — the `PipelineStage` wrapper; adapters are fetched
  from the `RuntimeContext` at execute time (registry is rebuilt worker-side —
  see the T10.6 serialization notes in `DefaultRuntimeContext`).
- `IngestionMain` — launcher (args: source URI, target table, project).

## Build & test

```bash
mvn -f deployments/original-data-to-bigqueryload-java/pom.xml test
```

Standalone Maven project (groupId `com.enrichmeai.culvert.deployments`, NOT in
the reactor) depending on the Culvert 0.1.0 artifacts — build the reactor first
if they are not in your local repository:

```bash
mvn -f data-pipeline-libraries-java/pom.xml install -DskipTests
```

## Status

Built and unit-tested (in-memory adapters; DirectRunner stage test). Not yet
exercised against live GCP — that is the deploy-and-test phase gating the 0.1.0
release (see `docs/framework-evolution/13-python-parity-release.md` §2). The
predecessor Python deployment was retired and removed in July 2026 (F1 legacy
cleanup; it survives in git history).
