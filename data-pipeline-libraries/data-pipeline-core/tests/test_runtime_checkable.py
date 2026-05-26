"""Test that Protocols are runtime_checkable.

`isinstance(obj, Protocol)` should work for any class that
structurally satisfies the Protocol. This is what lets Stage 2
implementations satisfy the contract by structural typing without
explicit inheritance.
"""

from datetime import date, datetime
from typing import Any, Iterator, List, Mapping, Optional

import pytest

from data_pipeline_core import (
    AuditEventPublisher,
    BlobStore,
    FinOpsSink,
    JobControlRepository,
    LineageEmitter,
    SecretProvider,
)
from data_pipeline_core.audit.records import AuditRecord
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics
from data_pipeline_core.job_control_api.models import (
    EntityStatus,
    FailedJob,
    FdpJobStatus,
    PipelineJob,
)
from data_pipeline_core.job_control_api.types import FailureStage, JobStatus
from data_pipeline_core.lineage.events import LineageEvent


class _FakeBlobStore:
    """Structural BlobStore impl — pure in-memory, no cloud."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def get(self, uri: str) -> bytes:
        return self._store[uri]

    def open(self, uri: str, mode: str = "rb") -> Any:
        raise NotImplementedError

    def put(self, uri: str, data: bytes) -> None:
        self._store[uri] = data

    def list(self, prefix: str) -> Iterator[str]:
        return (u for u in self._store if u.startswith(prefix))

    def exists(self, uri: str) -> bool:
        return uri in self._store

    def delete(self, uri: str) -> None:
        self._store.pop(uri, None)

    def copy(self, src: str, dst: str) -> None:
        self._store[dst] = self._store[src]


class _FakeSecretProvider:
    def __init__(self) -> None:
        self._secrets = {"db-password": "hunter2"}

    def get(self, name: str, version: str = "latest") -> str:
        return self._secrets[name]


class _FakeAuditEventPublisher:
    def __init__(self) -> None:
        self.published: List[AuditRecord] = []
        self.flushed = 0

    def publish(self, record: AuditRecord) -> None:
        self.published.append(record)

    def flush(self) -> None:
        self.flushed += 1


class _FakeLineageEmitter:
    def __init__(self) -> None:
        self.events: List[LineageEvent] = []

    def emit(self, event: LineageEvent) -> None:
        self.events.append(event)


class _FakeFinOpsSink:
    def __init__(self) -> None:
        self.records: List[tuple[CostMetrics, FinOpsTag]] = []

    def record(self, metrics: CostMetrics, tags: FinOpsTag) -> None:
        self.records.append((metrics, tags))


class _FakeJobControl:
    """Minimal in-memory JobControlRepository for runtime_checkable test.

    Implements every method on the Protocol; bodies are placeholder so
    the structural-subtype check passes.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, PipelineJob] = {}

    def create_job(self, job: PipelineJob) -> None:
        self._jobs[job.run_id] = job

    def get_job(self, run_id: str) -> Optional[PipelineJob]:
        return self._jobs.get(run_id)

    def update_status(
        self,
        run_id: str,
        status: JobStatus,
        total_records: Optional[int] = None,
    ) -> None:
        if run_id in self._jobs:
            self._jobs[run_id].status = status

    def mark_failed(
        self,
        run_id: str,
        error_code: str,
        error_message: str,
        failure_stage: FailureStage,
        error_file_path: Optional[str] = None,
    ) -> None:
        if run_id in self._jobs:
            self._jobs[run_id].status = JobStatus.FAILED

    def mark_retrying(self, run_id: str, retry_count: int) -> None:
        if run_id in self._jobs:
            self._jobs[run_id].status = JobStatus.RETRYING

    def get_pending_jobs(self, system_id: Optional[str] = None) -> List[PipelineJob]:
        return [j for j in self._jobs.values() if j.status in (JobStatus.CREATED, JobStatus.RUNNING)]

    def get_entity_status(self, system_id: str, extract_date: date) -> List[EntityStatus]:
        return []

    def get_failed_jobs(self, system_id: str, extract_date: date) -> List[FailedJob]:
        return []

    def get_fdp_job_status(
        self, system_id: str, extract_date: date, model_name: str
    ) -> Optional[FdpJobStatus]:
        return None

    def cleanup_partial_load(self, run_id: str, table_id: str) -> int:
        return 0

    def update_cost_metrics(
        self,
        run_id: str,
        estimated_cost_usd: float = 0.0,
        billed_bytes_scanned: int = 0,
        billed_bytes_written: int = 0,
    ) -> None:
        pass


def test_fake_blob_store_satisfies_protocol() -> None:
    assert isinstance(_FakeBlobStore(), BlobStore)


def test_fake_secret_provider_satisfies_protocol() -> None:
    assert isinstance(_FakeSecretProvider(), SecretProvider)


def test_fake_audit_publisher_satisfies_protocol() -> None:
    assert isinstance(_FakeAuditEventPublisher(), AuditEventPublisher)


def test_fake_lineage_emitter_satisfies_protocol() -> None:
    assert isinstance(_FakeLineageEmitter(), LineageEmitter)


def test_fake_finops_sink_satisfies_protocol() -> None:
    assert isinstance(_FakeFinOpsSink(), FinOpsSink)


def test_fake_job_control_satisfies_protocol() -> None:
    assert isinstance(_FakeJobControl(), JobControlRepository)


def test_partial_blob_store_does_not_satisfy_protocol() -> None:
    """A class missing `delete` should not pass isinstance against BlobStore."""

    class _IncompleteBlobStore:
        def get(self, uri: str) -> bytes:
            return b""

        def put(self, uri: str, data: bytes) -> None:
            pass

    # Note: runtime_checkable Protocols check for method names only, not signatures.
    # This test demonstrates the boundary: missing methods => not an instance.
    assert not isinstance(_IncompleteBlobStore(), BlobStore)
