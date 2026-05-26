# Mainframe Segment Transform (Java)

This is a Java implementation of the `mainframe-segment-transform` Dataflow pipeline, designed for heavy loads where the JVM's performance and threading model provide advantages over Python.

## Overview

The pipeline:
1.  Loads a segment definition from a YAML template.
2.  Executes a SQL query against BigQuery (CDP tables).
3.  Formats each row into a fixed-width string.
4.  Writes sharded files to GCS.
5.  Generates a JSON manifest file for the downstream mainframe processes.

## Comparison with Python Version

| Feature | Python | Java |
|---------|--------|------|
| Performance | Good for medium loads | Better for very large datasets |
| Startup Time | Faster | Slower (JVM overhead) |
| Type Safety | Dynamic (runtime) | Static (compile-time) |
| Logic | Matches exactly | Matches exactly |

## Configuration

Templates are compatible with the Python version. Both implementations use the same YAML structure for defining segments.

## Local Development

### Prerequisites
- Java 11
- Maven 3.9+
- GCP Credentials

### Build and Test
```bash
mvn clean test
```

### Running Locally (DirectRunner)
```bash
mvn compile exec:java \
  -Dexec.mainClass=com.enrichmeai.culvert.deployments.segmenttransform.MainframeSegmentPipeline \
  -Dexec.args="--templatePath=../mainframe-segment-transform/config/templates/customer.yaml \
               --extractDate=20260514 \
               --periodStart=2026-05-01 \
               --periodEnd=2026-05-31 \
               --outputBucket=my-output-bucket \
               --runner=DirectRunner"
```

## Deployment

Build and push the Flex Template using Cloud Build:
```bash
gcloud builds submit --config cloudbuild.yaml .
```
