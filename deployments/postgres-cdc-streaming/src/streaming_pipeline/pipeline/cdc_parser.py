"""
CDC Event Parser for Debezium Format

Parses Change Data Capture events from Debezium connector.
Supports PostgreSQL, MySQL, and other Debezium-supported databases.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Iterator

import apache_beam as beam
from apache_beam.metrics import Metrics


logger = logging.getLogger(__name__)


class ParseCDCEventDoFn(beam.DoFn):
    """
    Parse Debezium CDC events from Kafka/Pub/Sub.

    Debezium Event Structure:
    {
        "before": {...},      # Record state before change (null for INSERT)
        "after": {...},       # Record state after change (null for DELETE)
        "source": {
            "version": "2.4.0",
            "connector": "postgresql",
            "name": "pg-cdc",
            "ts_ms": 1709807400000,
            "db": "customers_db",
            "schema": "public",
            "table": "customers"
        },
        "op": "c",            # Operation: c=create, u=update, d=delete, r=read
        "ts_ms": 1709807400123
    }

    Outputs:
    - Parsed record with CDC metadata
    - _cdc_operation: INSERT, UPDATE, DELETE
    - _cdc_event_time: Timestamp of the change
    - _cdc_source_table: Source table name
    """

    def __init__(self):
        self.parse_success_counter = Metrics.counter("cdc_parser", "parse_success")
        self.parse_error_counter = Metrics.counter("cdc_parser", "parse_errors")
        self.insert_counter = Metrics.counter("cdc_parser", "inserts")
        self.update_counter = Metrics.counter("cdc_parser", "updates")
        self.delete_counter = Metrics.counter("cdc_parser", "deletes")

    def process(self, element: str) -> Iterator[Dict[str, Any]]:
        """
        Parse a single CDC event.

        Args:
            element: JSON string containing Debezium CDC event

        Yields:
            Parsed record with CDC metadata
        """
        try:
            event = json.loads(element)

            # Extract operation type
            operation = event.get("op")
            source = event.get("source", {})

            # Map Debezium operation to readable format
            if operation == "c":  # CREATE
                record = event.get("after", {})
                cdc_operation = "INSERT"
                self.insert_counter.inc()
            elif operation == "u":  # UPDATE
                record = event.get("after", {})
                cdc_operation = "UPDATE"
                self.update_counter.inc()
            elif operation == "d":  # DELETE
                record = event.get("before", {})
                cdc_operation = "DELETE"
                self.delete_counter.inc()
            elif operation == "r":  # READ (snapshot)
                record = event.get("after", {})
                cdc_operation = "SNAPSHOT"
            else:
                # Schema change or other event - skip
                logger.debug(f"Skipping non-data event: op={operation}")
                return

            if not record:
                logger.warning(f"Empty record for operation {operation}")
                return

            # Add CDC metadata to record
            record["_cdc_operation"] = cdc_operation
            record["_cdc_source_table"] = source.get("table")
            record["_cdc_source_db"] = source.get("db")
            record["_cdc_source_schema"] = source.get("schema")
            record["_cdc_connector"] = source.get("connector")
            record["_cdc_connector_version"] = source.get("version")

            # Parse event timestamp
            event_ts_ms = event.get("ts_ms", 0)
            if event_ts_ms:
                record["_cdc_event_time"] = datetime.fromtimestamp(
                    event_ts_ms / 1000, tz=timezone.utc
                ).isoformat()
            else:
                record["_cdc_event_time"] = datetime.now(tz=timezone.utc).isoformat()

            # Add source timestamp if available
            source_ts_ms = source.get("ts_ms", 0)
            if source_ts_ms:
                record["_cdc_source_time"] = datetime.fromtimestamp(
                    source_ts_ms / 1000, tz=timezone.utc
                ).isoformat()

            self.parse_success_counter.inc()
            yield record

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            self.parse_error_counter.inc()
            return
        except Exception as e:
            logger.error(f"Unexpected error parsing CDC event: {e}")
            self.parse_error_counter.inc()
            return


class ParseSimpleCDCDoFn(beam.DoFn):
    """
    Parse simplified CDC format (for testing or custom CDC implementations).

    Simple Format:
    {
        "operation": "INSERT|UPDATE|DELETE",
        "table": "customers",
        "timestamp": "2026-03-07T10:30:00Z",
        "data": {
            "customer_id": "C001",
            "name": "John Doe",
            ...
        }
    }
    """

    def process(self, element: str) -> Iterator[Dict[str, Any]]:
        try:
            event = json.loads(element)

            record = event.get("data", {})
            record["_cdc_operation"] = event.get("operation", "UNKNOWN")
            record["_cdc_source_table"] = event.get("table")
            record["_cdc_event_time"] = event.get("timestamp", datetime.now(tz=timezone.utc).isoformat())

            yield record

        except Exception as e:
            logger.error(f"Error parsing simple CDC event: {e}")
            return

