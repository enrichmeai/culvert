"""Smoke test for the supporting types referenced by the Protocols."""

from datetime import date, datetime, timezone

from data_pipeline_core.audit.records import AuditRecord
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics
from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import (
    MaskingPolicy,
    MaskingStrategy,
    RetentionPolicy,
)
from data_pipeline_core.job_control_api.models import PipelineJob
from data_pipeline_core.job_control_api.types import (
    FailureStage,
    JobStatus,
    JobType,
)
from data_pipeline_core.lineage.events import (
    LineageAudit,
    LineageDestination,
    LineageEvent,
    LineagePipeline,
    LineageSource,
)
from data_pipeline_core.schema.entity import EntitySchema, SchemaField


def test_pipeline_job_minimal_construction() -> None:
    job = PipelineJob(
        run_id="abc",
        system_id="sys",
        pipeline_name="p",
        extract_date=date(2026, 5, 26),
        status=JobStatus.CREATED,
    )
    assert job.job_type is JobType.INGESTION
    assert job.retry_count == 0


def test_audit_record_minimal_construction() -> None:
    record = AuditRecord(
        run_id="abc",
        pipeline_name="p",
        entity_type="customer",
        source_file="gs://b/p",
        record_count=42,
        processed_timestamp=datetime.now(timezone.utc),
        processing_duration_seconds=1.5,
        success=True,
    )
    assert record.error_count == 0
    assert record.audit_hash == ""
    assert record.metadata == {}


def test_cost_metrics_and_tag() -> None:
    metrics = CostMetrics(run_id="r")
    tag = FinOpsTag(
        system="retail",
        environment="prod",
        cost_center="cc1",
        owner="data-platform",
        run_id="r",
    )
    assert metrics.estimated_cost_usd == 0.0
    assert tag.extra == {}


def test_masking_policy_strategies() -> None:
    p = MaskingPolicy(strategy=MaskingStrategy.PARTIAL)
    assert p.replacement == "*"
    assert p.salt == ""
    assert MaskingStrategy.NONE.value == "none"


def test_retention_policy() -> None:
    r = RetentionPolicy(retention_days=2555)
    assert r.legal_hold is False
    assert r.purpose is None


def test_data_classification_values() -> None:
    assert DataClassification.PUBLIC.value == "public"
    assert DataClassification.RESTRICTED.value == "restricted"


def test_entity_schema() -> None:
    s = EntitySchema(
        name="customer",
        fields=[
            SchemaField(name="id", type="STRING", mode="REQUIRED"),
            SchemaField(name="email", type="STRING", classification=DataClassification.RESTRICTED),
        ],
        primary_key=["id"],
    )
    assert s.version == "1"
    assert len(s.fields) == 2
    assert s.fields[1].classification is DataClassification.RESTRICTED


def test_lineage_event_typeddict() -> None:
    # TypedDicts are just dicts at runtime.
    event: LineageEvent = {
        "source": LineageSource(type="file", uri="gs://b/p"),
        "pipeline": LineagePipeline(run_id="r", pipeline_name="p", stage="ingest"),
        "destination": LineageDestination(type="table", uri="bigquery://x.y.z"),
        "audit": LineageAudit(
            record_count_source=10,
            record_count_destination=10,
            error_count=0,
            audit_hash="hash",
        ),
    }
    assert event["pipeline"]["run_id"] == "r"
