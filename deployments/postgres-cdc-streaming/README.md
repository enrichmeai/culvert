# PostgreSQL CDC Streaming Pipeline

**Real-Time Streaming Pattern: PostgreSQL → Kafka → Beam (Streaming) → ODP → FDP**

> **Pattern Type:** STREAMING-CDC (Change Data Capture)

---

## Overview

This deployment demonstrates **real-time data streaming** from a PostgreSQL database to BigQuery, with immediate ODP-to-FDP transformation using Apache Beam's streaming capabilities.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        STREAMING CDC ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐    ┌─────────────────┐   │
│  │PostgreSQL│───▶│  Kafka   │───▶│  Apache Beam     │───▶│    BigQuery     │   │
│  │   CDC    │    │  Topics  │    │  (Streaming)     │    │   ODP + FDP     │   │
│  │(Debezium)│    │          │    │                  │    │                 │   │
│  └──────────┘    └──────────┘    └──────────────────┘    └─────────────────┘   │
│       │               │                   │                       │            │
│       │               │                   │                       │            │
│   Change          Message             Transform              Persist           │
│   Events          Queue               & Enrich               Real-time         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Flow Diagram

```
                         STREAMING CDC FLOW
                         ──────────────────

  PostgreSQL               Kafka                 Beam Streaming           BigQuery
  ──────────               ─────                 ──────────────           ────────

  ┌─────────────┐    ┌─────────────┐    ┌───────────────────────┐    ┌──────────┐
  │ Debezium    │    │ Topic:      │    │ 1. Read from Kafka    │    │ ODP      │
  │ Connector   │───▶│ pg.changes  │───▶│ 2. Parse CDC event    │───▶│ Tables   │
  │             │    │             │    │ 3. Transform record   │    │          │
  │ Captures:   │    │ Partitions  │    │ 4. Add audit columns  │    │ Streamed │
  │ • INSERT    │    │ by table    │    │ 5. Write to ODP       │    │ inserts  │
  │ • UPDATE    │    │             │    │                       │    │          │
  │ • DELETE    │    │             │    │ ────────────────────  │    └────┬─────┘
  └─────────────┘    └─────────────┘    │                       │         │
                                        │ 6. Window aggregation │         │
                                        │ 7. Apply FDP logic    │         ▼
                                        │ 8. Write to FDP       │    ┌──────────┐
                                        │                       │───▶│ FDP      │
                                        └───────────────────────┘    │ Tables   │
                                                                     │          │
                                                                     │ Real-time│
                                                                     │ views    │
                                                                     └──────────┘
```

---

## Pattern Details

### What Makes This Different from Batch

| Aspect | Batch (existing) | Streaming (this pattern) |
|--------|------------------|--------------------------|
| **Trigger** | File arrival (.ok file) | Continuous CDC events |
| **Latency** | Minutes to hours | Seconds to minutes |
| **Processing** | Bounded PCollection | Unbounded PCollection |
| **Windowing** | None (full file) | Tumbling/Sliding windows |
| **ODP Write** | Batch insert | Streaming insert |
| **FDP Transform** | Separate dbt job | Inline with streaming |

### CDC Event Structure (Debezium)

```json
{
  "before": null,
  "after": {
    "customer_id": "C001",
    "name": "John Doe",
    "email": "john@example.com",
    "status": "ACTIVE",
    "updated_at": "2026-03-07T10:30:00Z"
  },
  "source": {
    "version": "2.4.0",
    "connector": "postgresql",
    "name": "pg-cdc",
    "ts_ms": 1709807400000,
    "db": "customers_db",
    "schema": "public",
    "table": "customers"
  },
  "op": "c",  // c=create, u=update, d=delete
  "ts_ms": 1709807400123
}
```

---

## Components

```
deployments/postgres-cdc-streaming/
├── Dockerfile                    # Dataflow Flex Template
├── pyproject.toml
├── README.md
├── src/
│   └── streaming_pipeline/
│       ├── __init__.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── kafka_config.py   # Kafka connection settings
│       │   └── pipeline_config.py
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── runner.py         # Main streaming pipeline
│       │   ├── cdc_parser.py     # Parse Debezium CDC events
│       │   ├── transforms.py     # Streaming transforms
│       │   └── windows.py        # Windowing strategies
│       ├── schema/
│       │   ├── __init__.py
│       │   └── customers.py      # Entity schema
│       └── sinks/
│           ├── __init__.py
│           ├── odp_sink.py       # BigQuery streaming sink
│           └── fdp_sink.py       # FDP transformation sink
└── tests/
    └── unit/
        ├── test_cdc_parser.py
        ├── test_transforms.py
        └── test_windows.py
```

---

## Key Implementation

### 1. Main Streaming Pipeline (`runner.py`)

```python
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.kafka import ReadFromKafka
from apache_beam.transforms.window import FixedWindows, SlidingWindows
from apache_beam.transforms.trigger import AfterWatermark, AfterProcessingTime, AccumulationMode

from gcp_pipeline_core.audit import AuditTrailManager
from gcp_pipeline_beam.transforms import AddAuditColumnsDoFn

from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn
from streaming_pipeline.pipeline.transforms import TransformToODPDoFn, TransformToFDPDoFn
from streaming_pipeline.sinks.odp_sink import WriteToODPStreaming
from streaming_pipeline.sinks.fdp_sink import WriteToFDPStreaming


def run_streaming_pipeline(options):
    """
    Real-time CDC streaming pipeline.
    
    Flow: Kafka (CDC) → Parse → ODP → Window → FDP
    """
    pipeline_options = PipelineOptions(options)
    pipeline_options.view_as(StandardOptions).streaming = True  # Enable streaming mode
    
    with beam.Pipeline(options=pipeline_options) as p:
        # =====================================================================
        # Step 1: Read CDC events from Kafka
        # =====================================================================
        cdc_events = (
            p
            | "ReadFromKafka" >> ReadFromKafka(
                consumer_config={
                    "bootstrap.servers": options.kafka_bootstrap_servers,
                    "group.id": options.kafka_consumer_group,
                    "auto.offset.reset": "earliest",
                },
                topics=[options.kafka_topic],
                with_metadata=True,
            )
            | "ExtractValue" >> beam.Map(lambda kv: kv[1].decode("utf-8"))
        )
        
        # =====================================================================
        # Step 2: Parse CDC events (Debezium format)
        # =====================================================================
        parsed_records = (
            cdc_events
            | "ParseCDCEvent" >> beam.ParDo(ParseCDCEventDoFn())
            | "FilterValidRecords" >> beam.Filter(lambda r: r is not None)
        )
        
        # =====================================================================
        # Step 3: Transform and write to ODP (immediate)
        # =====================================================================
        odp_records = (
            parsed_records
            | "TransformToODP" >> beam.ParDo(TransformToODPDoFn())
            | "AddAuditColumns" >> beam.ParDo(AddAuditColumnsDoFn(
                run_id=options.run_id,
                source="kafka-cdc"
            ))
        )
        
        # Write to ODP using streaming inserts
        odp_records | "WriteToODP" >> WriteToODPStreaming(
            project=options.project,
            dataset="odp_streaming",
            table=options.entity_name,
        )
        
        # =====================================================================
        # Step 4: Window for FDP aggregation
        # =====================================================================
        windowed_records = (
            odp_records
            | "ApplyWindow" >> beam.WindowInto(
                FixedWindows(60),  # 1-minute windows
                trigger=AfterWatermark(
                    early=AfterProcessingTime(10),  # Early firing every 10s
                ),
                accumulation_mode=AccumulationMode.DISCARDING,
            )
        )
        
        # =====================================================================
        # Step 5: Transform to FDP (within window)
        # =====================================================================
        fdp_records = (
            windowed_records
            | "TransformToFDP" >> beam.ParDo(TransformToFDPDoFn())
        )
        
        # Write to FDP
        fdp_records | "WriteToFDP" >> WriteToFDPStreaming(
            project=options.project,
            dataset="fdp_streaming",
            table=f"{options.entity_name}_summary",
        )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--kafka_bootstrap_servers", required=True)
    parser.add_argument("--kafka_topic", required=True)
    parser.add_argument("--kafka_consumer_group", default="beam-streaming-cdc")
    parser.add_argument("--entity_name", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--run_id", default=None)
    
    known_args, pipeline_args = parser.parse_known_args()
    run_streaming_pipeline(known_args)
```

### 2. CDC Event Parser (`cdc_parser.py`)

```python
import json
import apache_beam as beam
from datetime import datetime
from typing import Optional, Dict, Any


class ParseCDCEventDoFn(beam.DoFn):
    """
    Parse Debezium CDC events from Kafka.
    
    Handles:
    - INSERT (op='c'): New record created
    - UPDATE (op='u'): Record modified
    - DELETE (op='d'): Record deleted
    """
    
    def process(self, element: str) -> Optional[Dict[str, Any]]:
        try:
            event = json.loads(element)
            
            operation = event.get("op")
            source = event.get("source", {})
            
            # Extract record data based on operation
            if operation == "c":  # CREATE
                record = event.get("after", {})
                record["_cdc_operation"] = "INSERT"
            elif operation == "u":  # UPDATE
                record = event.get("after", {})
                record["_cdc_operation"] = "UPDATE"
            elif operation == "d":  # DELETE
                record = event.get("before", {})
                record["_cdc_operation"] = "DELETE"
            else:
                # Schema change or other event - skip
                return
            
            # Add CDC metadata
            record["_cdc_source_table"] = source.get("table")
            record["_cdc_source_db"] = source.get("db")
            record["_cdc_event_time"] = datetime.fromtimestamp(
                event.get("ts_ms", 0) / 1000
            ).isoformat()
            record["_cdc_connector"] = source.get("connector")
            
            yield record
            
        except json.JSONDecodeError as e:
            # Log bad message and continue
            beam.metrics.Metrics.counter("cdc", "parse_errors").inc()
            return
        except Exception as e:
            beam.metrics.Metrics.counter("cdc", "unexpected_errors").inc()
            return
```

### 3. Windowing Strategies (`windows.py`)

```python
import apache_beam as beam
from apache_beam.transforms.window import (
    FixedWindows,
    SlidingWindows,
    Sessions,
    GlobalWindows,
)
from apache_beam.transforms.trigger import (
    AfterWatermark,
    AfterProcessingTime,
    AfterCount,
    Repeatedly,
    AccumulationMode,
)


class StreamingWindowStrategies:
    """
    Windowing strategies for different FDP transformation patterns.
    """
    
    @staticmethod
    def minute_tumbling():
        """
        1-minute fixed windows with early firing.
        Good for: Real-time dashboards, minute-level aggregations.
        """
        return beam.WindowInto(
            FixedWindows(60),
            trigger=AfterWatermark(
                early=AfterProcessingTime(10),  # Fire every 10 seconds
            ),
            accumulation_mode=AccumulationMode.DISCARDING,
            allowed_lateness=300,  # 5 minutes late data allowed
        )
    
    @staticmethod
    def sliding_average(window_size=300, slide_interval=60):
        """
        5-minute sliding windows, sliding every 1 minute.
        Good for: Moving averages, trend detection.
        """
        return beam.WindowInto(
            SlidingWindows(window_size, slide_interval),
            trigger=AfterWatermark(),
            accumulation_mode=AccumulationMode.DISCARDING,
        )
    
    @staticmethod
    def session_based(gap_duration=600):
        """
        Session windows with 10-minute gap.
        Good for: User sessions, activity tracking.
        """
        return beam.WindowInto(
            Sessions(gap_duration),
            trigger=AfterWatermark(
                early=AfterCount(100),  # Fire after 100 records
            ),
            accumulation_mode=AccumulationMode.ACCUMULATING,
        )
    
    @staticmethod
    def micro_batch(batch_size=1000, max_wait_seconds=30):
        """
        Global window with count/time trigger (micro-batching).
        Good for: High-throughput with batched writes.
        """
        return beam.WindowInto(
            GlobalWindows(),
            trigger=Repeatedly(
                AfterCount(batch_size) | AfterProcessingTime(max_wait_seconds)
            ),
            accumulation_mode=AccumulationMode.DISCARDING,
        )
```

### 4. FDP Transform (Inline) (`transforms.py`)

```python
import apache_beam as beam
from typing import Dict, Any, Iterable
from datetime import datetime


class TransformToFDPDoFn(beam.DoFn):
    """
    Transform ODP records to FDP format inline with streaming.
    
    This replaces the separate dbt transformation for real-time use cases.
    """
    
    def __init__(self, mask_pii: bool = True):
        self.mask_pii = mask_pii
    
    def process(self, element: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """
        Apply FDP transformation logic.
        
        For complex JOINs, use side inputs or state.
        """
        fdp_record = {
            # Business key
            "customer_id": element.get("customer_id"),
            
            # Transformed fields
            "full_name": f"{element.get('first_name', '')} {element.get('last_name', '')}".strip(),
            "email_domain": self._extract_email_domain(element.get("email")),
            "status": element.get("status"),
            
            # PII masking (inline)
            "ssn_masked": self._mask_ssn(element.get("ssn")) if self.mask_pii else element.get("ssn"),
            
            # CDC metadata preserved
            "cdc_operation": element.get("_cdc_operation"),
            "cdc_event_time": element.get("_cdc_event_time"),
            
            # FDP audit
            "fdp_processed_at": datetime.utcnow().isoformat(),
            "run_id": element.get("_run_id"),
        }
        
        yield fdp_record
    
    def _extract_email_domain(self, email: str) -> str:
        if email and "@" in email:
            return email.split("@")[1]
        return ""
    
    def _mask_ssn(self, ssn: str) -> str:
        if ssn and len(ssn) >= 4:
            return f"XXX-XX-{ssn[-4:]}"
        return "XXX-XX-XXXX"


class AggregatePerWindowDoFn(beam.DoFn):
    """
    Aggregate records within a window for FDP summary tables.
    """
    
    def process(self, element, window=beam.DoFn.WindowParam):
        """
        Create window-level aggregations.
        """
        window_start = window.start.to_utc_datetime().isoformat()
        window_end = window.end.to_utc_datetime().isoformat()
        
        # element is a tuple (key, records) from GroupByKey
        key, records = element
        record_list = list(records)
        
        yield {
            "window_start": window_start,
            "window_end": window_end,
            "group_key": key,
            "record_count": len(record_list),
            "insert_count": sum(1 for r in record_list if r.get("_cdc_operation") == "INSERT"),
            "update_count": sum(1 for r in record_list if r.get("_cdc_operation") == "UPDATE"),
            "delete_count": sum(1 for r in record_list if r.get("_cdc_operation") == "DELETE"),
            "processed_at": datetime.utcnow().isoformat(),
        }
```

---

## Infrastructure Requirements

### GCP Services

| Service | Purpose |
|---------|---------|
| **Cloud SQL (PostgreSQL)** | Source database with CDC enabled |
| **Pub/Sub or Confluent Kafka** | Message queue for CDC events |
| **Dataflow** | Streaming Beam runner |
| **BigQuery** | ODP + FDP storage |

### Kafka Setup (Confluent or self-managed)

```yaml
# docker-compose.yml for local development
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
  
  debezium:
    image: debezium/connect:2.4
    depends_on:
      - kafka
    ports:
      - "8083:8083"
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: debezium-cluster
      CONFIG_STORAGE_TOPIC: debezium_configs
      OFFSET_STORAGE_TOPIC: debezium_offsets
      STATUS_STORAGE_TOPIC: debezium_status
```

### Debezium Connector Configuration

```json
{
  "name": "postgres-cdc-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "cdc_user",
    "database.password": "${secrets.postgres_password}",
    "database.dbname": "customers_db",
    "database.server.name": "pg-cdc",
    "table.include.list": "public.customers,public.accounts",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_slot",
    "publication.name": "debezium_publication",
    "topic.prefix": "pg-cdc",
    "transforms": "route",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "([^.]+)\\.([^.]+)\\.([^.]+)",
    "transforms.route.replacement": "cdc.$3"
  }
}
```

---

## Running the Pipeline

### Local Development

```bash
# Start Kafka + Debezium
docker-compose up -d

# Run pipeline locally
python src/streaming_pipeline/pipeline/runner.py \
    --kafka_bootstrap_servers=localhost:9092 \
    --kafka_topic=cdc.customers \
    --entity_name=customers \
    --project=your-project-id \
    --runner=DirectRunner
```

### Dataflow (Production)

```bash
python src/streaming_pipeline/pipeline/runner.py \
    --kafka_bootstrap_servers=kafka.internal:9092 \
    --kafka_topic=cdc.customers \
    --entity_name=customers \
    --project=your-project-id \
    --runner=DataflowRunner \
    --region=europe-west2 \
    --temp_location=gs://your-bucket/temp \
    --streaming \
    --enable_streaming_engine \
    --num_workers=2 \
    --max_num_workers=10
```

---

## Comparison: Batch vs Streaming

| Aspect | Batch Pipeline | Streaming Pipeline |
|--------|----------------|-------------------|
| **Trigger** | File arrival | Continuous CDC |
| **Latency** | Minutes-hours | Seconds |
| **Orchestration** | Airflow DAGs | Self-running (Dataflow) |
| **FDP Transform** | Separate dbt job | Inline with Beam |
| **Error Handling** | Error bucket | Dead letter queue |
| **Scaling** | Job-based | Auto-scaling |
| **Cost** | Per-job | Continuous (streaming) |

---

## When to Use This Pattern

✅ **Use Streaming CDC When:**
- Real-time dashboards needed
- Sub-minute latency required
- Source is a transactional database
- Continuous data flow (not batch files)

❌ **Stick with Batch When:**
- Data arrives as files (mainframe extracts)
- Latency of minutes/hours is acceptable
- Complex multi-table JOINs required
- Cost optimization is priority

