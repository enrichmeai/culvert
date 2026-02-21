# CDP Segmentation Reference Implementation

This deployment demonstrates a **Consumable Data Product (CDP)** pipeline using Apache Beam on Google Cloud Dataflow.

## Overview

The CDP pipeline performs the following steps:
1.  **Read from Multiple Sources**: Reads multiple Foundation Data Product (FDP) tables from BigQuery in parallel.
2.  **Segmentation & Processing**: Applies custom logic to segment the data (e.g., by region) and normalize fields for downstream consumption.
3.  **Segmented GCS Export**: Writes the results to Google Cloud Storage as segmented JSONL files, ensuring scalability for large datasets.

## Structure

- `src/cdp_example/main.py`: The main pipeline code using the `gcp-pipeline-beam` library's fluent API.
- `requirements.txt`: Python dependencies for the pipeline.

## Usage

### Local Execution (for testing)

Ensure you have your GCP credentials configured and the library paths added to your `PYTHONPATH`.

```bash
export PYTHONPATH=$PYTHONPATH:../../gcp-pipeline-libraries/gcp-pipeline-core/src:../../gcp-pipeline-libraries/gcp-pipeline-beam/src

python3 src/cdp_example/main.py \
    --project your-project-id \
    --dataset your_fdp_dataset \
    --tables table1,table2 \
    --bucket your-output-bucket \
    --prefix cdp_exports \
    --segment_size 1000 \
    --runner DirectRunner
```

### Dataflow Execution

```bash
python3 src/cdp_example/main.py \
    --project your-project-id \
    --dataset your_fdp_dataset \
    --tables table1,table2 \
    --bucket your-output-bucket \
    --prefix cdp_exports \
    --segment_size 10000 \
    --runner DataflowRunner \
    --region us-central1 \
    --temp_location gs://your-temp-bucket/temp
```

## Key Features

- **Parallel Reads**: Uses the enhanced `ReadFromBigQueryDoFn` to read from multiple BigQuery tables simultaneously.
- **Scalable Writing**: Uses `WriteSegmentedToGCSDoFn` to avoid memory issues when exporting large amounts of data.
- **Fluent API**: Leverages `BeamPipelineBuilder` for clean and readable pipeline definitions.
