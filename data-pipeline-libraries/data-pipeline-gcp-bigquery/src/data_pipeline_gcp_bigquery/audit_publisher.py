"""BigQueryAuditEventPublisher - AuditEventPublisher Protocol backed by BigQuery DML.

Java sibling: ``com.enrichmeai.culvert.gcp.bigquery.BigQueryAuditEventPublisher``
(data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/
com/enrichmeai/culvert/gcp/bigquery/BigQueryAuditEventPublisher.java)

Each :meth:`publish` writes one row of ``job_control.audit_events`` (the ten
columns of docs/CONTRACT.md section 4, as the Terraform in
``infrastructure/terraform/systems/generic/main.tf`` declares them) with one
parameterised ``INSERT ... VALUES`` statement, and waits for it. Writes go
straight through, so :meth:`flush` has nothing to do.

A failed write is never silent. A run-level event raises: the event is the
run's state, and continuing without it is how a run reports a success it never
had. An aggregate event logs at ERROR, with the whole event, and returns, so an
audit hiccup over a counter cannot halt ingestion. As in Java, the failed
aggregate is not yet dead-lettered to a blob.

#257.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.cloud import bigquery

from data_pipeline_core.audit.events import AuditEvent

logger = logging.getLogger(__name__)

# The dataset the repository provisions, and the table in it - Java DEFAULT_DATASET / DEFAULT_TABLE.
DEFAULT_DATASET = "job_control"
DEFAULT_TABLE = "audit_events"

_COLUMNS = (
    "run_id, system_id, entity, event_kind, event_ts, extract_date, "
    "payload, producer, contract_version, environment"
)
_VALUES = (
    "@run_id, @system_id, @entity, @event_kind, @event_ts, @extract_date, "
    "PARSE_JSON(@payload), @producer, @contract_version, @environment"
)


class BigQueryAuditEventPublisher:
    """AuditEventPublisher writing to a BigQuery ``audit_events`` table.

    Mirrors ``com.enrichmeai.culvert.gcp.bigquery.BigQueryAuditEventPublisher``.
    Pass a pre-built ``google.cloud.bigquery.Client``; this class does not
    close it.
    """

    def __init__(
        self,
        client: Any,
        project_id: str,
        dataset: str = DEFAULT_DATASET,
        table: str = DEFAULT_TABLE,
    ) -> None:
        """
        :param client:     Pre-built ``google.cloud.bigquery.Client``. Required.
        :param project_id: GCP project ID. Required.
        :param dataset:    BigQuery dataset. Defaults to ``"job_control"``.
        :param table:      BigQuery table. Defaults to ``"audit_events"``.
        :raises TypeError: if any argument is None.
        """
        for name, value in (("client", client), ("project_id", project_id),
                            ("dataset", dataset), ("table", table)):
            if value is None:
                raise TypeError(f"{name} must not be None")
        self._client = client
        self._project_id = project_id
        self._fqtn = f"`{project_id}.{dataset}.{table}`"
        self._failures = 0

    # --- AuditEventPublisher Protocol --------------------------------------

    def publish(self, event: AuditEvent) -> None:
        """Write one event and wait for the write.

        :raises TypeError: if event is None.
        :raises RuntimeError: if the write of a run-level event failed; the
            BigQuery error is its ``__cause__``.
        """
        if event is None:
            raise TypeError("event must not be None")

        sql = f"INSERT INTO {self._fqtn} ({_COLUMNS}) VALUES ({_VALUES})"
        try:
            # Inside the try: a payload JSON cannot encode fails like a failed write.
            config = bigquery.QueryJobConfig(query_parameters=_parameters(event))
            self._client.query(sql, job_config=config).result()
        except Exception as error:
            self._failures += 1
            if event.failure_is_fatal():
                raise RuntimeError(
                    f"Audit publish FAILED for run-level event {event.event_kind.wire_value} "
                    f"run_id={event.run_id} -> {self._fqtn}. Failing the pipeline rather "
                    "than reporting a success that was never recorded."
                ) from error
            logger.error(
                "Audit publish failed for aggregate event %s run_id=%s entity=%s payload=%s; "
                "ingestion continues, event recoverable from this log",
                event.event_kind.wire_value, event.run_id, event.entity, dict(event.payload),
                exc_info=error,
            )

    def flush(self) -> None:
        """Write-through: there is no buffer to flush."""

    # --- observability ------------------------------------------------------

    @property
    def audit_failure_count(self) -> int:
        """Writes that failed since this publisher was built, run-level or aggregate."""
        return self._failures

    @property
    def project_id(self) -> str:
        return self._project_id


def _string(name: str, value: Any) -> bigquery.ScalarQueryParameter:
    return bigquery.ScalarQueryParameter(name, "STRING", value)


def _parameters(event: AuditEvent) -> list:
    return [
        _string("run_id", event.run_id),
        _string("system_id", event.system_id),
        _string("entity", event.entity),
        _string("event_kind", event.event_kind.wire_value),
        bigquery.ScalarQueryParameter("event_ts", "TIMESTAMP", event.event_ts),
        bigquery.ScalarQueryParameter("extract_date", "DATE", event.extract_date),
        # A value JSON has no type for (a datetime, a Decimal) is written as its text. Nested
        # maps and lists become real JSON, where Java writes their toString(). NaN and Infinity
        # are refused (PARSE_JSON would reject them), as is a circular payload.
        _string("payload", json.dumps(dict(event.payload), default=str, allow_nan=False)),
        _string("producer", event.producer),
        _string("contract_version", event.contract_version),
        _string("environment", event.environment),
    ]
