"""
Streaming CDC Transform DoFns.

Transforms CDC records through two stages:
- ODP (Operational Data Platform): raw CDC record with audit columns
- FDP (Feature Data Platform): enriched, PII-masked, windowed record
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Iterator

import apache_beam as beam
from apache_beam.metrics import Metrics

logger = logging.getLogger(__name__)


class TransformToODPDoFn(beam.DoFn):
    """
    Transform a parsed CDC record for ODP ingestion.

    ODP receives the full CDC record with metadata intact.
    Field names are normalised (no entity-specific renaming — that belongs
    in FDP or in a deployment-level subclass).

    Outputs the record unchanged except for stripping any None values
    that would fail BigQuery NOT NULL constraints.
    """

    def __init__(self):
        self.success_counter = Metrics.counter("odp_transform", "success")
        self.error_counter = Metrics.counter("odp_transform", "errors")

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        try:
            # Remove keys whose value is None to avoid schema conflicts;
            # BigQuery NULLABLE columns handle absence of key correctly.
            record = {k: v for k, v in element.items() if v is not None}
            self.success_counter.inc()
            yield record
        except Exception as exc:
            logger.error("TransformToODPDoFn error: %s", exc)
            self.error_counter.inc()


class TransformToFDPDoFn(beam.DoFn):
    """
    Transform an ODP record to FDP format.

    FDP applies:
    - PII masking for regulated fields (SSN, email)
    - Field renaming / derived fields (full_name, email_domain)
    - Window boundary injection (populated via WindowedValue in process context)

    Args:
        mask_pii: When True, mask SSN and email fields.
    """

    def __init__(self, mask_pii: bool = True):
        self.mask_pii = mask_pii
        self.success_counter = Metrics.counter("fdp_transform", "success")
        self.error_counter = Metrics.counter("fdp_transform", "errors")

    def process(self, element: Dict[str, Any], window=beam.DoFn.WindowParam) -> Iterator[Dict[str, Any]]:
        try:
            record: Dict[str, Any] = {}

            # Primary key
            record["customer_id"] = element.get("customer_id")

            # Derived fields
            first = element.get("first_name", "")
            last = element.get("last_name", "")
            name = element.get("name", "")
            record["full_name"] = f"{first} {last}".strip() if (first or last) else name

            # Email domain extraction
            email = element.get("email", "")
            if email and "@" in email:
                record["email_domain"] = email.split("@", 1)[1] if not self.mask_pii else "****"
            else:
                record["email_domain"] = None

            record["status"] = element.get("status")

            # PII masking
            ssn = element.get("ssn", "")
            if self.mask_pii and ssn:
                record["ssn_masked"] = f"XXX-XX-{str(ssn)[-4:]}" if len(str(ssn)) >= 4 else "XXX-XX-****"
            else:
                record["ssn_masked"] = ssn or None

            # Window boundaries
            try:
                record["window_start"] = window.start.to_utc_datetime().isoformat()
                record["window_end"] = window.end.to_utc_datetime().isoformat()
            except Exception:
                # GlobalWindow or non-windowed context
                now = datetime.now(tz=timezone.utc).isoformat()
                record["window_start"] = now
                record["window_end"] = now

            # Preserve CDC metadata
            record["cdc_operation"] = element.get("_cdc_operation")
            record["cdc_event_time"] = element.get("_cdc_event_time")

            self.success_counter.inc()
            yield record

        except Exception as exc:
            logger.error("TransformToFDPDoFn error: %s", exc)
            self.error_counter.inc()


class AddStreamingAuditDoFn(beam.DoFn):
    """
    Inject audit columns into every streaming record.

    Adds:
    - _run_id: the pipeline run identifier
    - _processed_at: ISO timestamp at processing time
    """

    def __init__(self, run_id: str):
        self.run_id = run_id

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        record = dict(element)
        record["_run_id"] = self.run_id
        record["_processed_at"] = datetime.now(tz=timezone.utc).isoformat()
        yield record
