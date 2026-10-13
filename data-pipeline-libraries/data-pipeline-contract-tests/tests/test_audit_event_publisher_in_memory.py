"""AuditEventPublisherContract against an in-memory reference publisher (#257).

The reference shows the suite can be passed; the swallowing publisher shows it
catches the defect the Protocol exists to forbid: a run-level failure that is
logged and dropped, so a run reports a success that was never recorded.
"""

from __future__ import annotations

import logging

import pytest

from data_pipeline_contract_tests import AuditEventPublisherContract
from data_pipeline_contract_tests.audit_event_publisher import contract_event
from data_pipeline_core.audit.events import EventKind


class _Backend:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.rows: list = []

    def write(self, event) -> None:
        if self.fail:
            raise ConnectionError("backend down")
        self.rows.append(event)


class _ReferencePublisher:
    def __init__(self, backend: _Backend) -> None:
        self._backend = backend

    def publish(self, event) -> None:
        try:
            self._backend.write(event)
        except Exception:
            if event.failure_is_fatal():
                raise
            logging.getLogger(__name__).error("aggregate audit event lost: %s", event)

    def flush(self) -> None:
        pass


class _SwallowingPublisher(_ReferencePublisher):
    def publish(self, event) -> None:
        try:
            self._backend.write(event)
        except Exception:
            pass


class TestReferencePublisher(AuditEventPublisherContract):
    @pytest.fixture
    def backend(self):
        return _Backend()

    @pytest.fixture
    def publisher(self, backend):
        return _ReferencePublisher(backend)

    @pytest.fixture
    def failing_publisher(self):
        return _ReferencePublisher(_Backend(fail=True))

    @pytest.fixture
    def delivered(self, backend):
        return lambda: len(backend.rows)


def test_the_suite_catches_a_publisher_that_swallows_a_run_level_failure():
    suite = AuditEventPublisherContract()
    with pytest.raises(pytest.fail.Exception):
        suite.test_a_failed_run_level_publish_raises(
            _SwallowingPublisher(_Backend(fail=True)), EventKind.RUN_END)


def test_the_contract_event_carries_every_required_payload_key():
    for kind in EventKind:
        assert set(kind.required_payload_keys) <= set(contract_event(kind).payload)
