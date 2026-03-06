# CSV Parsing and BigQuery Error Handling Guide

## Overview

This guide covers robust error handling for CSV parsing and BigQuery operations in the GCP Pipeline Framework. These components address common issues in mainframe-to-cloud data migrations:

- **CSV Parsing Issues**: Missing columns, non-UTF8 characters, wrong delimiters, corrupted rows
- **BigQuery Errors**: Quota exceeded, rate limits, table locks, load job timeouts

## CSV Parsing with RobustCsvParseDoFn

### The Problem

Legacy mainframe extracts often have data quality issues:

1. **Missing columns** - Rows with fewer fields than expected
2. **Extra columns** - Rows with more fields than expected  
3. **Non-UTF8 characters** - EBCDIC artifacts, Latin-1 encoding issues
4. **Wrong delimiters** - Mixed or unexpected field separators
5. **Corrupted rows** - Truncated data, embedded newlines, null bytes
6. **Quote mismatches** - Unbalanced quotes in quoted fields

### Solution: RobustCsvParseDoFn

```python
from gcp_pipeline_beam.pipelines.beam.transforms import (
    RobustCsvParseDoFn,
    CSVParserConfig,
    CSVErrorType,
)

# Configure the parser
config = CSVParserConfig(
    field_names=['customer_id', 'name', 'email', 'account_balance'],
    delimiter=',',
    skip_hdr_trl=True,           # Skip HDR|/TRL| records from mainframe
    strict_field_count=False,    # Pad missing fields, truncate extra
    detect_delimiter=True,       # Auto-detect if configured delimiter fails
    sanitize_encoding=True,      # Clean non-UTF8 characters
    max_field_length=65535,      # Detect corruption
)

# Use in pipeline with tagged outputs
parsed = (
    lines 
    | 'ParseCSV' >> beam.ParDo(RobustCsvParseDoFn(config))
        .with_outputs('main', 'errors', 'warnings')
)

# Handle outputs
valid_records = parsed.main
error_records = parsed.errors      # Failed to parse
warning_records = parsed.warnings  # Parsed with fixes (e.g., encoding cleaned)
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `field_names` | Required | List of expected column names |
| `delimiter` | `,` | Expected field delimiter |
| `skip_hdr_trl` | `True` | Skip HDR/TRL records |
| `strict_field_count` | `False` | If True, reject rows with wrong field count |
| `detect_delimiter` | `True` | Auto-detect delimiter if parsing fails |
| `sanitize_encoding` | `True` | Replace non-UTF8 characters |
| `max_field_length` | `65535` | Flag corruption if field exceeds this |
| `strip_null_bytes` | `True` | Remove null bytes from data |

### Error Types

The parser classifies errors using `CSVErrorType`:

- `FIELD_COUNT_MISMATCH` - Wrong number of fields
- `MISSING_COLUMNS` - Fewer fields than expected  
- `EXTRA_COLUMNS` - More fields than expected
- `ENCODING_ERROR` - Cannot decode as UTF-8
- `WRONG_DELIMITER` - Parsing failed with all delimiters
- `CORRUPTED_ROW` - Row appears corrupted
- `QUOTE_MISMATCH` - Unbalanced quotes
- `NULL_BYTE` - Null bytes detected

---

## BigQuery Retry Logic

### The Problem

BigQuery operations can fail with transient errors that Beam's native retries don't handle optimally:

1. **Quota exceeded** - Daily/hourly limits hit
2. **Rate limits** - Too many requests per second
3. **Table locks** - Concurrent writes blocking each other
4. **Backend errors** - Temporary service issues
5. **Timeouts** - Long operations timing out

### Solution: ResilientWriteToBigQueryDoFn

```python
from gcp_pipeline_beam.pipelines.beam.io import (
    ResilientWriteToBigQueryDoFn,
    BatchResilientWriteToBigQueryDoFn,
    BigQueryRetryConfig,
    BigQueryErrorType,
)

# Configure retry behavior
retry_config = BigQueryRetryConfig(
    max_retries=5,
    initial_delay_seconds=1.0,
    max_delay_seconds=300.0,       # 5 minute max backoff
    backoff_multiplier=2.0,        # Exponential backoff
    quota_retry_delay=60.0,        # Wait longer for quota errors
    table_lock_retry_delay=30.0,   # Wait for table locks
    dead_letter_after_retries=True # Route to DLQ after max retries
)

# Single-record writer with retry logic
written = (
    records
    | 'WriteBQ' >> beam.ParDo(
        ResilientWriteToBigQueryDoFn(
            project='my-project',
            dataset='my_dataset',
            table='my_table',
            config=retry_config,
            run_id=run_id
        )
    ).with_outputs('main', 'retryable', 'dead_letter', 'errors')
)

# Handle outputs
success = written.main
dead_letter = written.dead_letter  # Retryable errors after max retries
errors = written.errors            # Non-retryable errors (bad data)
```

### Batched Writes for Better Performance

For high-volume ingestion, use the batched writer:

```python
written = (
    records
    | 'BatchWriteBQ' >> beam.ParDo(
        BatchResilientWriteToBigQueryDoFn(
            project='my-project',
            dataset='my_dataset',
            table='my_table',
            batch_size=500,
            config=retry_config,
            run_id=run_id
        )
    ).with_outputs('main', 'dead_letter', 'errors')
)
```

### Error Classification

The classifier automatically determines retry strategy:

| Error Type | Retryable | Typical Cause |
|------------|-----------|---------------|
| `QUOTA_EXCEEDED` | ✅ | Project quota limits |
| `RATE_LIMIT` | ✅ | Too many requests |
| `TABLE_LOCK` | ✅ | Concurrent writes |
| `BACKEND_ERROR` | ✅ | Service issues |
| `TIMEOUT` | ✅ | Long operations |
| `INVALID_DATA` | ❌ | Bad data values |
| `SCHEMA_MISMATCH` | ❌ | Wrong data types |
| `NOT_FOUND` | ❌ | Missing table |
| `PERMISSION_DENIED` | ❌ | Access issues |

### Metrics

Both writers emit metrics for monitoring:

- `bq_retry_write/success` - Successfully written records
- `bq_retry_write/retried` - Records that were retried
- `bq_retry_write/dead_letter` - Records sent to DLQ
- `bq_retry_write/errors` - Non-retryable errors
- `bq_retry_write/quota_errors` - Quota-related errors
- `bq_retry_write/lock_errors` - Table lock errors
- `bq_retry_write/timeout_errors` - Timeout errors

---

## Complete Pipeline Example

```python
"""Example pipeline with robust CSV parsing and BigQuery retry logic."""

from gcp_pipeline_beam.pipelines.beam.transforms import (
    RobustCsvParseDoFn,
    CSVParserConfig,
)
from gcp_pipeline_beam.pipelines.beam.io import (
    ResilientWriteToBigQueryDoFn,
    BigQueryRetryConfig,
)

# CSV Parser Configuration
csv_config = CSVParserConfig(
    field_names=['id', 'name', 'email', 'balance'],
    delimiter=',',
    skip_hdr_trl=True,
    strict_field_count=False,
    detect_delimiter=True,
    sanitize_encoding=True,
)

# BigQuery Retry Configuration
bq_config = BigQueryRetryConfig(
    max_retries=5,
    quota_retry_delay=60.0,
)

with beam.Pipeline(options=pipeline_options) as p:
    # Read and parse CSV
    lines = p | 'ReadGCS' >> beam.io.ReadFromText(input_pattern)
    
    parsed = (
        lines 
        | 'ParseCSV' >> beam.ParDo(RobustCsvParseDoFn(csv_config))
            .with_outputs('main', 'errors', 'warnings')
    )
    
    # Write valid records to BigQuery with retry
    written = (
        parsed.main
        | 'WriteBQ' >> beam.ParDo(
            ResilientWriteToBigQueryDoFn(
                project=project_id,
                dataset='odp_data',
                table=entity_name,
                config=bq_config,
                run_id=run_id
            )
        ).with_outputs('main', 'dead_letter', 'errors')
    )
    
    # Write CSV parse errors to error table
    _ = (
        parsed.errors
        | 'WriteParseErrors' >> beam.io.WriteToBigQuery(
            f'{project_id}:error_tracking.csv_parse_errors',
            write_disposition='WRITE_APPEND'
        )
    )
    
    # Write BQ dead letter records for later retry
    _ = (
        written.dead_letter
        | 'WriteDLQ' >> beam.io.WriteToText(
            f'gs://{project_id}-dlq/{run_id}/bq_failures'
        )
    )
```

---

## Error Handling Best Practices

### 1. Use Tagged Outputs

Always use `.with_outputs()` to capture all error streams:

```python
results = (
    records 
    | beam.ParDo(MyDoFn()).with_outputs('main', 'errors', 'warnings')
)
```

### 2. Log Error Details

Include context in error records:

```python
{
    'record': original_record,
    'error': error_message,
    'error_type': 'QUOTA_EXCEEDED',
    'retry_count': 3,
    'run_id': run_id,
    'timestamp': datetime.utcnow().isoformat()
}
```

### 3. Monitor Retry Metrics

Set up alerts on retry metrics:

```python
# Cloud Monitoring query
SELECT
  metric.labels.error_type,
  COUNT(*) as error_count
FROM `project.dataflow_job.user_metrics`
WHERE metric.type = 'bq_retry_write/dead_letter'
GROUP BY error_type
```

### 4. Configure Appropriate Delays

Tune delays based on your workload:

- **High-priority ingestion**: Lower delays, more retries
- **Batch processing**: Higher delays, fewer retries
- **Quota-constrained**: Much longer quota delays

---

## Related Documentation

- [ERROR_HANDLING_GUIDE.md](./ERROR_HANDLING_GUIDE.md) - General error handling patterns
- [COMPLETE_TESTING_GUIDE.md](./COMPLETE_TESTING_GUIDE.md) - Testing error scenarios
- [DATA_QUALITY_GUIDE.md](./DATA_QUALITY_GUIDE.md) - Data quality validation

