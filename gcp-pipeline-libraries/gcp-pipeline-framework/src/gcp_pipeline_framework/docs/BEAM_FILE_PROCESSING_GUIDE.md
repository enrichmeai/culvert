# Apache Beam File Processing & Docker Resource Guide

> **Last Updated:** March 2026  
> **Version:** 1.0

This guide provides comprehensive guidance on Apache Beam file processing capacity limits, memory management, and Docker resource configuration for optimal pipeline performance.

---

## Table of Contents

1. [Overview](#overview)
2. [File Size Limits & Recommendations](#file-size-limits--recommendations)
3. [Memory & CPU Guidelines](#memory--cpu-guidelines)
4. [Docker Resource Configuration](#docker-resource-configuration)
5. [Dataflow Worker Configuration](#dataflow-worker-configuration)
6. [Large File Processing Strategies](#large-file-processing-strategies)
7. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
8. [Configuration Examples](#configuration-examples)

---

## Overview

Apache Beam's file processing capacity depends on several factors:

| Factor | Impact |
|--------|--------|
| **Runner** | DirectRunner (local), DataflowRunner (GCP), FlinkRunner |
| **Worker Memory** | Determines max file size that can be held in memory |
| **Worker Type** | CPU cores affect parallelism |
| **File Format** | CSV, JSON, Avro, Parquet have different memory profiles |
| **Compression** | Compressed files require decompression memory overhead |

### Key Principle

> **Apache Beam processes data in parallel streams, not by loading entire files into memory.** However, certain operations (windowing, grouping, large records) can require significant memory.

---

## File Size Limits & Recommendations

### Per-File Size Guidelines

| File Size | Recommendation | Worker Type (Dataflow) | Memory |
|-----------|----------------|------------------------|--------|
| **< 100 MB** | Standard processing | `n1-standard-2` | 7.5 GB |
| **100 MB - 1 GB** | Standard processing | `n1-standard-4` | 15 GB |
| **1 GB - 10 GB** | Large file handling | `n1-standard-8` | 30 GB |
| **10 GB - 100 GB** | Split files recommended | `n1-highmem-8` | 52 GB |
| **> 100 GB** | **Must split files** | `n1-highmem-16` | 104 GB |

### Record Size Guidelines

| Record Size | Processing Notes |
|-------------|------------------|
| **< 1 KB** | Standard - no special handling |
| **1 KB - 100 KB** | Standard - ensure adequate memory |
| **100 KB - 1 MB** | Large records - increase worker memory |
| **1 MB - 10 MB** | Very large - use streaming reads |
| **> 10 MB** | **Consider redesigning data model** |

### CSV-Specific Considerations

```
┌─────────────────────────────────────────────────────────────────┐
│  CSV File Processing Memory Formula                             │
│                                                                  │
│  Memory Required ≈ (File Size × 3) + (Record Count × Overhead)  │
│                                                                  │
│  Where:                                                          │
│  - File Size × 3: Parse + Transform + Output buffers            │
│  - Overhead: ~500 bytes per record for metadata                 │
└─────────────────────────────────────────────────────────────────┘
```

**Example Calculations:**

| CSV File | Records | Est. Memory | Recommended Worker |
|----------|---------|-------------|-------------------|
| 50 MB | 100K | ~200 MB | `n1-standard-2` (7.5 GB) |
| 500 MB | 1M | ~2 GB | `n1-standard-4` (15 GB) |
| 5 GB | 10M | ~20 GB | `n1-standard-8` (30 GB) |
| 50 GB | 100M | ~200 GB | Split into 10 files |

---

## Memory & CPU Guidelines

### Memory Requirements by Operation

| Operation | Memory Multiplier | Notes |
|-----------|-------------------|-------|
| **Read File** | 1x file size | Streaming read is memory-efficient |
| **Parse CSV** | 2-3x record size | String parsing overhead |
| **Schema Validation** | 1.5x record size | Type conversion buffers |
| **GroupByKey** | Varies | Can be very high for large groups |
| **CoGroupByKey** | Sum of all inputs | Join operations are memory-intensive |
| **Window Aggregation** | Window size × records | Bounded by window duration |
| **Write BigQuery** | Batch size × record | Default batch: 500 records |

### CPU Requirements

| Pipeline Type | CPU Cores | Reasoning |
|---------------|-----------|-----------|
| **Simple ETL** | 2-4 cores | Read → Transform → Write |
| **Complex Transforms** | 4-8 cores | Multiple branching paths |
| **ML Feature Engineering** | 8-16 cores | Vectorized operations |
| **Real-time Streaming** | 4-8 cores | Low latency requirements |

---

## Docker Resource Configuration

### Local Development (Docker Desktop)

Update Docker Desktop settings or `docker-compose.yml`:

```yaml
# docker-compose.yml - Resource Limits
services:
  beam-pipeline:
    image: ingestion-pipeline:latest
    deploy:
      resources:
        limits:
          # For files up to 500 MB
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    environment:
      - JAVA_OPTS=-Xmx6g -Xms2g
      - BEAM_WORKER_MEMORY_MB=6144
```

### Resource Profiles by File Size

#### Profile: Small Files (< 100 MB)

```yaml
# docker-compose.small.yml
services:
  ingestion-pipeline:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    environment:
      - BEAM_DIRECT_NUM_WORKERS=2
      - BEAM_DIRECT_RUNNING_MODE=multi_threading
```

#### Profile: Medium Files (100 MB - 1 GB)

```yaml
# docker-compose.medium.yml
services:
  ingestion-pipeline:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    environment:
      - BEAM_DIRECT_NUM_WORKERS=4
      - BEAM_DIRECT_RUNNING_MODE=multi_threading
```

#### Profile: Large Files (1 GB - 10 GB)

```yaml
# docker-compose.large.yml
services:
  ingestion-pipeline:
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 16G
        reservations:
          cpus: '4'
          memory: 8G
    environment:
      - BEAM_DIRECT_NUM_WORKERS=8
      - BEAM_DIRECT_RUNNING_MODE=multi_threading
```

#### Profile: Very Large Files (> 10 GB)

```yaml
# docker-compose.xlarge.yml
services:
  ingestion-pipeline:
    deploy:
      resources:
        limits:
          cpus: '16'
          memory: 32G
        reservations:
          cpus: '8'
          memory: 16G
    environment:
      - BEAM_DIRECT_NUM_WORKERS=16
      - BEAM_DIRECT_RUNNING_MODE=multi_threading
```

### Dockerfile Optimizations for Large Files

```dockerfile
# Optimized Dockerfile for Large File Processing
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for performance
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    # For faster CSV parsing
    libcsv-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with performance optimizations
RUN pip install --no-cache-dir \
    apache-beam[gcp]==2.56.0 \
    # Fast CSV parsing
    pyarrow \
    fastparquet \
    # Memory-efficient processing
    dask[dataframe] \
    # Compression support
    lz4 \
    zstandard

# Install shared libraries
RUN pip install --no-cache-dir \
    gcp-pipeline-framework[core,beam]>=1.0.6

# Copy deployment code
COPY deployments/original-data-to-bigqueryload /app/deployments/original-data-to-bigqueryload

# Install deployment
RUN pip install -e /app/deployments/original-data-to-bigqueryload

# Configure Python for large file handling
ENV PYTHONUNBUFFERED=1
ENV PYTHONHASHSEED=random
# Increase Python recursion limit for deep data structures
ENV PYTHONDONTWRITEBYTECODE=1

# Memory optimization settings
ENV MALLOC_TRIM_THRESHOLD_=131072
ENV MALLOC_MMAP_MAX_=65536

# Beam configuration
ENV BEAM_DIRECT_NUM_WORKERS=4
ENV BEAM_DIRECT_RUNNING_MODE=multi_threading

# Set entrypoint
ENTRYPOINT ["python", "-m", "data_ingestion.pipeline.runner"]
```

---

## Dataflow Worker Configuration

### Machine Type Selection

```python
# Pipeline options for different file sizes
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, WorkerOptions

def get_pipeline_options(file_size_mb: int) -> PipelineOptions:
    """Get optimized pipeline options based on expected file size."""
    
    options = PipelineOptions()
    worker_options = options.view_as(WorkerOptions)
    
    if file_size_mb < 100:
        # Small files
        worker_options.machine_type = 'n1-standard-2'
        worker_options.num_workers = 1
        worker_options.max_num_workers = 3
        worker_options.disk_size_gb = 50
        
    elif file_size_mb < 1000:
        # Medium files (up to 1 GB)
        worker_options.machine_type = 'n1-standard-4'
        worker_options.num_workers = 2
        worker_options.max_num_workers = 10
        worker_options.disk_size_gb = 100
        
    elif file_size_mb < 10000:
        # Large files (up to 10 GB)
        worker_options.machine_type = 'n1-highmem-8'
        worker_options.num_workers = 4
        worker_options.max_num_workers = 20
        worker_options.disk_size_gb = 200
        
    else:
        # Very large files (> 10 GB)
        worker_options.machine_type = 'n1-highmem-16'
        worker_options.num_workers = 8
        worker_options.max_num_workers = 50
        worker_options.disk_size_gb = 500
        # Use SSD for faster disk I/O
        worker_options.disk_type = 'compute.googleapis.com/projects//zones//diskTypes/pd-ssd'
    
    return options
```

### Dataflow Flex Template Configuration

```json
{
  "image": "gcr.io/${PROJECT_ID}/ingestion-pipeline:latest",
  "sdkInfo": {
    "language": "PYTHON"
  },
  "metadata": {
    "name": "Mainframe Ingestion Pipeline",
    "description": "Ingests mainframe files to BigQuery ODP layer",
    "parameters": [
      {
        "name": "source_file",
        "label": "Input file pattern",
        "helpText": "GCS path pattern for input files",
        "isOptional": false
      },
      {
        "name": "worker_machine_type",
        "label": "Worker machine type",
        "helpText": "GCE machine type (e.g., n1-standard-4, n1-highmem-8)",
        "isOptional": true,
        "regexes": ["^n[12]-(standard|highmem|highcpu)-[0-9]+$"]
      },
      {
        "name": "max_num_workers",
        "label": "Maximum workers",
        "helpText": "Maximum number of Dataflow workers",
        "isOptional": true,
        "regexes": ["^[0-9]+$"]
      }
    ]
  },
  "defaultEnvironment": {
    "machineType": "n1-standard-4",
    "maxWorkers": 10,
    "numWorkers": 2
  }
}
```

---

## Large File Processing Strategies

### Strategy 1: File Splitting (Recommended for > 10 GB)

Split large files before processing:

```python
# File splitting utility
from gcp_pipeline_core.utils import split_large_file

def split_if_needed(gcs_path: str, max_size_mb: int = 1000) -> list[str]:
    """
    Split large files into smaller chunks.
    
    Args:
        gcs_path: GCS path to the file
        max_size_mb: Maximum size per chunk in MB
        
    Returns:
        List of GCS paths to split files
    """
    from google.cloud import storage
    
    client = storage.Client()
    blob = storage.Blob.from_string(gcs_path, client=client)
    
    file_size_mb = blob.size / (1024 * 1024)
    
    if file_size_mb <= max_size_mb:
        return [gcs_path]
    
    # Split logic - creates files like: original_part001.csv, original_part002.csv
    num_parts = int(file_size_mb / max_size_mb) + 1
    return split_large_file(gcs_path, num_parts)
```

### Strategy 2: Streaming Read with Batching

```python
import apache_beam as beam
from apache_beam.io import ReadFromText

class BatchedReadDoFn(beam.DoFn):
    """
    Read and batch records for memory-efficient processing.
    
    Processes records in batches to control memory usage.
    """
    
    def __init__(self, batch_size: int = 10000):
        self.batch_size = batch_size
    
    def process(self, element, *args, **kwargs):
        # Process in batches
        batch = []
        for record in element:
            batch.append(record)
            if len(batch) >= self.batch_size:
                yield batch
                batch = []
        
        if batch:
            yield batch


# Usage in pipeline
def create_batched_pipeline(input_pattern: str):
    """Create pipeline with batched processing for large files."""
    
    with beam.Pipeline() as p:
        records = (
            p
            | "Read" >> ReadFromText(input_pattern)
            | "Batch" >> beam.ParDo(BatchedReadDoFn(batch_size=10000))
            | "Process Batch" >> beam.FlatMap(process_batch)
            | "Write" >> beam.io.WriteToBigQuery(...)
        )
```

### Strategy 3: Parallel File Processing

```python
import apache_beam as beam
from apache_beam.io.filesystems import FileSystems

def get_file_shards(pattern: str) -> list[str]:
    """Get all files matching pattern."""
    return [m.path for m in FileSystems.match([pattern])[0].metadata_list]


def create_parallel_pipeline(input_pattern: str):
    """
    Process multiple files in parallel.
    
    Each file is processed by separate workers.
    """
    
    with beam.Pipeline() as p:
        # Get list of files
        files = get_file_shards(input_pattern)
        
        # Process each file independently
        results = (
            p
            | "Create File List" >> beam.Create(files)
            | "Process Files" >> beam.ParDo(ProcessFileDoFn())
            | "Flatten Results" >> beam.Flatten()
            | "Write" >> beam.io.WriteToBigQuery(...)
        )
```

### Strategy 4: Compressed File Handling

```python
import apache_beam as beam
from apache_beam.io import ReadFromText
from apache_beam.io.filesystem import CompressionTypes

# Beam automatically handles common compression formats
pipeline = beam.Pipeline()

# GZIP files (*.gz)
gzip_records = (
    pipeline
    | "Read GZIP" >> ReadFromText(
        "gs://bucket/file.csv.gz",
        compression_type=CompressionTypes.GZIP
    )
)

# BZIP2 files (*.bz2)
bzip_records = (
    pipeline
    | "Read BZIP2" >> ReadFromText(
        "gs://bucket/file.csv.bz2",
        compression_type=CompressionTypes.BZIP2
    )
)

# Memory consideration for compressed files:
# - GZIP: ~10x decompression ratio (100 MB compressed → 1 GB in memory)
# - BZIP2: ~15x decompression ratio
# - LZ4: ~3x decompression ratio (fastest)
```

---

## Monitoring & Troubleshooting

### Memory Monitoring Commands

```bash
# Docker container memory usage
docker stats ingestion-pipeline

# Detailed memory breakdown
docker exec ingestion-pipeline cat /proc/meminfo

# Check for OOM kills
docker inspect ingestion-pipeline | grep -i oom
```

### Dataflow Job Monitoring

```bash
# View Dataflow job metrics
gcloud dataflow jobs describe JOB_ID --region=europe-west2 --format=json

# Check worker logs for memory issues
gcloud logging read "resource.type=dataflow_step AND severity>=WARNING" \
    --project=$PROJECT_ID \
    --limit=100
```

### Common Issues & Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **OOM Kill** | Container exits with code 137 | Increase memory limit in Docker config |
| **Slow Processing** | Pipeline takes >10x expected time | Increase CPU cores or workers |
| **Disk Full** | "No space left on device" | Increase `disk_size_gb` in worker options |
| **Worker Starvation** | Some workers idle | Reduce batch size, increase shuffle memory |
| **Shuffle Timeout** | "Shuffle read timed out" | Use SSD disks, increase `shuffle_service_options` |

### Performance Tuning Checklist

```bash
# 1. Check file size
gsutil du -sh gs://bucket/your-file.csv

# 2. Estimate records
gsutil cat gs://bucket/your-file.csv | wc -l

# 3. Calculate required memory
# Rule of thumb: Memory = FileSize × 3 + (RecordCount × 0.0005 GB)

# 4. Select appropriate Docker profile
docker-compose -f docker-compose.medium.yml up

# 5. Monitor during processing
docker stats --no-stream

# 6. Check for errors
docker logs ingestion-pipeline 2>&1 | grep -i "error\|warning\|memory"
```

---

## Configuration Examples

### Example 1: Small Daily Batches (< 100 MB)

```yaml
# docker-compose.daily.yml
version: '3.8'
services:
  ingestion-pipeline:
    image: ingestion-pipeline:latest
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    environment:
      - INPUT_PATTERN=gs://bucket/daily/*.csv
      - BATCH_SIZE=5000
      - NUM_WORKERS=2
```

### Example 2: Weekly Large Batches (1-5 GB)

```yaml
# docker-compose.weekly.yml
version: '3.8'
services:
  ingestion-pipeline:
    image: ingestion-pipeline:latest
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 16G
    environment:
      - INPUT_PATTERN=gs://bucket/weekly/*.csv
      - BATCH_SIZE=20000
      - NUM_WORKERS=8
      - MACHINE_TYPE=n1-highmem-8
```

### Example 3: Full Historical Load (> 50 GB)

```yaml
# docker-compose.historical.yml
version: '3.8'
services:
  ingestion-pipeline:
    image: ingestion-pipeline:latest
    deploy:
      resources:
        limits:
          cpus: '16'
          memory: 32G
    environment:
      - INPUT_PATTERN=gs://bucket/historical/*.csv
      - BATCH_SIZE=50000
      - NUM_WORKERS=16
      - MACHINE_TYPE=n1-highmem-16
      - MAX_NUM_WORKERS=50
      - DISK_SIZE_GB=500
      - USE_SSD=true
```

### Example 4: Dataflow Flex Template Launch

```bash
#!/bin/bash
# launch_large_file_pipeline.sh

FILE_SIZE_MB=$(gsutil du -s $INPUT_FILE | awk '{print int($1/1048576)}')

if [ $FILE_SIZE_MB -lt 100 ]; then
    MACHINE_TYPE="n1-standard-2"
    MAX_WORKERS=3
elif [ $FILE_SIZE_MB -lt 1000 ]; then
    MACHINE_TYPE="n1-standard-4"
    MAX_WORKERS=10
elif [ $FILE_SIZE_MB -lt 10000 ]; then
    MACHINE_TYPE="n1-highmem-8"
    MAX_WORKERS=20
else
    MACHINE_TYPE="n1-highmem-16"
    MAX_WORKERS=50
fi

gcloud dataflow flex-template run "ingestion-$(date +%Y%m%d-%H%M%S)" \
    --template-file-gcs-location="gs://${PROJECT_ID}-dataflow-templates/ingestion-template.json" \
    --region="europe-west2" \
    --parameters="source_file=${INPUT_FILE}" \
    --parameters="worker_machine_type=${MACHINE_TYPE}" \
    --parameters="max_num_workers=${MAX_WORKERS}" \
    --service-account-email="${SERVICE_ACCOUNT}"
```

---

## Quick Reference Card

### File Size → Docker Memory Mapping

| File Size | Docker Memory | Docker CPU | Dataflow Worker |
|-----------|---------------|------------|-----------------|
| 10 MB | 2G | 1 | n1-standard-1 |
| 100 MB | 4G | 2 | n1-standard-2 |
| 500 MB | 8G | 4 | n1-standard-4 |
| 1 GB | 12G | 4 | n1-standard-4 |
| 5 GB | 16G | 8 | n1-highmem-8 |
| 10 GB | 24G | 8 | n1-highmem-8 |
| 50 GB | Split files | - | n1-highmem-16 × N |

### Memory Formula

```
Docker Memory = max(4GB, FileSize × 4)
Dataflow Memory = max(7.5GB, FileSize × 3)
```

### Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEAM_DIRECT_NUM_WORKERS` | Local worker count | 1 |
| `BEAM_DIRECT_RUNNING_MODE` | Threading mode | `multi_threading` |
| `BEAM_WORKER_MEMORY_MB` | Worker memory limit | 4096 |
| `BATCH_SIZE` | Records per batch | 10000 |

---

## Related Documentation

- [Infrastructure Requirements Guide](INFRASTRUCTURE_REQUIREMENTS.md)
- [GCP Deployment Guide](GCP_DEPLOYMENT_GUIDE.md)
- [Docker Compose Guide](DOCKER_COMPOSE_GUIDE.md)
- [Error Handling Guide](ERROR_HANDLING_GUIDE.md)
- [FinOps Strategy](FINOPS_STRATEGY.md)

---

*This guide is maintained by the Platform Team. For questions, see [PLATFORM_TEAM_INFO.md](../PLATFORM_TEAM_INFO.md).*

