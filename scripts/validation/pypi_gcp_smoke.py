#!/usr/bin/env python3
"""Post-release validation: the published `culvert[gcp]` wheel against real GCP.

Sprint 25. Exercises every Python GCP adapter in the PyPI-published wheel
against the live culvert demo project — the coverage gap the release left
(the GCP deploy proved the JAVA adapters; Python's ran only against unit
mocks). Run from an environment with ADC (Tier 2) or as a Cloud Run job:

    python -m venv /tmp/vsmoke && /tmp/vsmoke/bin/pip install 'culvert[gcp]'
    /tmp/vsmoke/bin/python scripts/validation/pypi_gcp_smoke.py culvert-501806

Each check uses the ADAPTER (not the raw google client) for the operation
under test; raw clients appear only for scratch setup/teardown. Scratch
resources are created and deleted; total cost is ~£0 (all free-tier).
Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
import time
import uuid


def main(project: str) -> int:
    results: list[tuple[str, str]] = []
    run_id = f"smoke-{uuid.uuid4().hex[:8]}"
    failures = 0

    def check(name: str, fn) -> None:
        nonlocal failures
        try:
            detail = fn()
            results.append((name, f"PASS — {detail}"))
        except Exception as exc:  # noqa: BLE001 — report every adapter's outcome
            failures += 1
            results.append((name, f"FAIL — {type(exc).__name__}: {exc}"))

    # ---- 1. entry-point discovery (the wheel's wiring) --------------------
    def discovery():
        from data_pipeline_core import autoconfig

        cfg = autoconfig.discover()
        names = ["blob_store", "warehouse", "finops", "source", "sink",
                 "secrets", "observability", "stage_metrics", "lineage"]
        missing = [n for n in names if cfg.first(n) is None]
        assert not missing, f"unloadable: {missing}"
        return "all 9 adapters discoverable"

    check("autoconfig discovery", discovery)

    # ---- 2. GcsBlobStore ---------------------------------------------------
    def gcs():
        from google.cloud import storage
        from data_pipeline_gcp_gcs import GcsBlobStore

        store = GcsBlobStore(storage.Client(project=project))
        uri = f"gs://{project}-generic-int-temp/smoke/{run_id}.txt"
        payload = f"culvert pypi smoke {run_id}".encode()
        store.put(uri, payload)
        assert store.exists(uri)
        assert store.get(uri) == payload
        store.delete(uri)
        assert not store.exists(uri)
        return f"put/get/exists/delete round-trip on {uri}"

    check("GcsBlobStore", gcs)

    # ---- 3. BigQueryWarehouse ----------------------------------------------
    def bq():
        from google.cloud import bigquery
        from data_pipeline_gcp_bigquery import BigQueryWarehouse

        wh = BigQueryWarehouse(project, bigquery.Client(project=project))
        assert wh.table_exists(f"{project}.job_control.pipeline_jobs")
        rows = list(wh.query(
            f"SELECT COUNT(*) AS n FROM `{project}.job_control.pipeline_jobs`", None))
        n = rows[0]["n"]
        assert n >= 1, "expected job-control rows from the earlier deploy"
        return f"table_exists + query — {n} historic pipeline runs visible"

    check("BigQueryWarehouse", bq)

    # ---- 4. PubSubSink + PubSubSource ---------------------------------------
    def pubsub():
        from google.cloud import pubsub_v1
        from data_pipeline_gcp_pubsub import PubSubSink, PubSubSource

        publisher, subscriber = pubsub_v1.PublisherClient(), pubsub_v1.SubscriberClient()
        topic = publisher.topic_path(project, f"culvert-{run_id}")
        sub = subscriber.subscription_path(project, f"culvert-{run_id}")
        publisher.create_topic(name=topic)
        try:
            subscriber.create_subscription(name=sub, topic=topic)
            PubSubSink(publisher, topic).write(
                iter([{"data": f"hello-{run_id}".encode(),
                       "attributes": {"origin": "pypi-smoke"}}]))
            time.sleep(3)
            msgs = list(PubSubSource(subscriber, sub, max_messages=5).read())
            assert any(f"hello-{run_id}".encode() == m.get("data") for m in msgs), \
                f"published message not received: {msgs!r}"
            return "publish via PubSubSink, receive via PubSubSource (scratch topic)"
        finally:
            subscriber.delete_subscription(subscription=sub)
            publisher.delete_topic(topic=topic)

    check("PubSubSink/PubSubSource", pubsub)

    # ---- 5. SecretManagerProvider -------------------------------------------
    def secrets():
        from google.cloud import secretmanager
        from data_pipeline_gcp_secrets import SecretManagerProvider

        raw = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{project}"
        sid = f"culvert-{run_id}"
        raw.create_secret(parent=parent, secret_id=sid,
                          secret={"replication": {"automatic": {}}})
        try:
            raw.add_secret_version(parent=f"{parent}/secrets/{sid}",
                                   payload={"data": b"s3cret-smoke"})
            value = SecretManagerProvider(project_id=project).get(sid)
            assert value == "s3cret-smoke"
            return "secret read back through the adapter (scratch secret)"
        finally:
            raw.delete_secret(name=f"{parent}/secrets/{sid}")

    check("SecretManagerProvider", secrets)

    # ---- 6. CloudMonitoringMetricsHook ---------------------------------------
    def monitoring():
        from google.cloud import monitoring_v3
        from data_pipeline_core.contracts.stage_metrics import StageMetrics
        from data_pipeline_gcp_observability import CloudMonitoringMetricsHook

        hook = CloudMonitoringMetricsHook(
            monitoring_v3.MetricServiceClient(), project)
        hook.record_stage_metrics(StageMetrics(
            pipeline_id="pypi-smoke", run_id=run_id, stage_name="validate",
            rows_processed=1, stage_latency_ms=1.0, error_count=0))
        # The hook swallows emission errors by design (resilience contract), so
        # a clean return proves nothing — READ THE SERIES BACK. This is what
        # caught the monitoring_v3.MetricDescriptor removal the first time.
        # New metric descriptors can take minutes to index — poll.
        client = monitoring_v3.MetricServiceClient()
        got = []
        for _ in range(8):
            time.sleep(20)
            end = time.time()
            try:
                got = list(client.list_time_series(request={
            "name": f"projects/{project}",
            "filter": (f'metric.type="custom.googleapis.com/culvert/rows_processed" '
                       f'AND metric.labels.run_id="{run_id}"'),
            "interval": {"end_time": {"seconds": int(end)},
                          "start_time": {"seconds": int(end) - 600}},
            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }))
            except Exception:
                got = []
            if got:
                break
        assert got, "metric not found on read-back — emission silently failed"
        return f"StageMetrics written AND read back ({len(got)} series)"

    check("CloudMonitoringMetricsHook", monitoring)

    # ---- report --------------------------------------------------------------
    print(f"\nculvert[gcp] (PyPI wheel) vs real GCP — project {project}, run {run_id}\n")
    for name, outcome in results:
        print(f"  {'✓' if outcome.startswith('PASS') else '✗'} {name}: {outcome}")
    print(f"\n{len(results) - failures}/{len(results)} adapters PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "culvert-501806"))
