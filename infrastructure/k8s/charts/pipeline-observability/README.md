# pipeline-observability Helm Chart

A Helm chart for deploying OpenTelemetry collector, Prometheus, and Grafana for comprehensive pipeline observability.

## Install

```bash
helm install pipeline-observability ./pipeline-observability \
  --namespace pipeline \
  --create-namespace
```

## Components

- **OTEL Collector** — Receives telemetry via gRPC (4317) and HTTP (4318), exports to GCP Monitoring and Jaeger
- **Prometheus** — Metrics collection and retention (15 days default)
- **Grafana** — Dashboards for visualization

## Pointing Pipeline Code at the Collector

Set the OTEL endpoint in your pipeline code:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://pipeline-observability-otel-collector:4317
```

Or configure in Python:

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

exporter = OTLPSpanExporter(
    endpoint="http://pipeline-observability-otel-collector:4317"
)
trace_provider = TracerProvider()
trace_provider.add_span_processor(BatchSpanProcessor(exporter))
```

## Accessing Grafana

```bash
kubectl port-forward svc/pipeline-observability-grafana 3000:3000 -n pipeline
```

Open http://localhost:3000 (default: admin / admin)

## Grafana Dashboards

Seven dashboards are bundled in the `grafana-dashboards-configmap.yaml` ConfigMap and auto-provisioned into Grafana on install.

| Dashboard file | Title | Description |
|---|---|---|
| `pipeline-overview.json` | Pipeline Overview | Top-level pipeline health — service `up` status. |
| `per-entity-throughput.json` | Per-Entity Throughput | Records ingested per entity per hour; total (24h stat); top-10 entities by volume (7d bar chart). |
| `per-entity-error-rate.json` | Per-Entity Error Rate | Rejection rate time-series per entity; current overall error-rate stat; latest 25 audit-event failures (BigQuery table). |
| `per-run-cost.json` | Per-Run Cost (FinOps) | Cost by service over time (stacked); MTD spend stat; top-10 entity costs (30d bar chart); cost heatmap by hour-of-day. |
| `reconciliation-health.json` | Reconciliation Health | GREEN/YELLOW/RED status counts (stats); RED record trend by day (30d); most recent 10 failures with expected vs valid counts (BigQuery table). |
| `data-quality-grades.json` | Data Quality Grades | A–F grade distribution stacked by day (30d); A/B pass-rate stat (7d); per-entity average grade score bar chart (30d). |
| `airflow-scheduler-health.json` | Airflow Scheduler Health | Scheduler heartbeat lag stat; queued vs running task count time-series; DAG parse P50/P95 time-series; top-5 longest-running tasks table (24h). |

All dashboards use `schemaVersion: 38`, `timezone: "browser"`, and template variables for `system_id`, `environment`, and `entity` (multi-value, defaults to All). Prometheus panels use `${DS_PROMETHEUS}`; BigQuery panels use `${DS_BIGQUERY}`.

## Cleanup

```bash
helm uninstall pipeline-observability -n pipeline
```
