#!/bin/bash
# Quick Trigger Script - Run LOA Pipeline Now
# This is the easiest way to trigger the pipeline

set -e

PROJECT_ID="loa-migration-dev"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           🚀 TRIGGERING LOA PIPELINE NOW                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Verify sample data
echo "📋 Step 1: Checking for input data..."
FILE_COUNT=$(gsutil ls gs://${PROJECT_ID}-loa-data/input/*.csv 2>/dev/null | wc -l)

if [ $FILE_COUNT -eq 0 ]; then
    echo "⚠️  No CSV files found. Uploading sample data..."
    gsutil cp data/input/applications_20250119_1.csv gs://${PROJECT_ID}-loa-data/input/
    echo "✅ Sample data uploaded"
else
    echo "✅ Found $FILE_COUNT CSV file(s) ready to process"
    gsutil ls gs://${PROJECT_ID}-loa-data/input/
fi

echo ""

# Step 2: Install dependencies if needed
echo "📦 Step 2: Checking dependencies..."
if ! python3 -c "import apache_beam" 2>/dev/null; then
    echo "⚙️  Installing Apache Beam and dependencies..."
    pip3 install -q -r requirements-ci.txt
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

echo ""

# Step 3: Run the pipeline
echo "🚀 Step 3: Running pipeline (DirectRunner - FREE)..."
echo ""

# Simple approach: Use Python directly
python3 << 'PIPELINE_SCRIPT'
import sys
sys.path.insert(0, '/path/to/project')

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from loa_common.validation import validate_application_record
from loa_common.schema import get_applications_raw_schema, get_applications_errors_schema
from datetime import datetime
import csv
import json

# Configuration
PROJECT_ID = "loa-migration-dev"
DATASET = "loa_migration"
INPUT_PATTERN = f"gs://{PROJECT_ID}-loa-data/input/applications_*.csv"
OUTPUT_TABLE = f"{PROJECT_ID}:{DATASET}.applications_raw"
ERROR_TABLE = f"{PROJECT_ID}:{DATASET}.applications_errors"
RUN_ID = f"manual-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

print(f"📝 Pipeline Configuration:")
print(f"   Project:    {PROJECT_ID}")
print(f"   Input:      {INPUT_PATTERN}")
print(f"   Output:     {OUTPUT_TABLE}")
print(f"   Errors:     {ERROR_TABLE}")
print(f"   Run ID:     {RUN_ID}")
print("")

class ParseCSV(beam.DoFn):
    """Parse CSV lines into dictionaries."""

    def process(self, element):
        """
        Args:
            element: tuple of (filename, line_content)
        """
        filename, line = element

        # Skip header lines
        if line.startswith('application_id'):
            return

        try:
            # Parse CSV line
            reader = csv.DictReader([line], fieldnames=[
                'application_id', 'ssn', 'applicant_name',
                'loan_amount', 'loan_type', 'application_date', 'branch_code'
            ])
            record = next(reader)

            # Add source metadata
            record['_source_file'] = filename.split('/')[-1]

            yield record
        except Exception as e:
            # Yield error record
            yield beam.pvalue.TaggedOutput('parse_errors', {
                'source_file': filename.split('/')[-1],
                'error': f"Parse error: {str(e)}",
                'raw_line': line
            })

class ValidateAndEnrich(beam.DoFn):
    """Validate records and enrich with metadata."""

    def __init__(self, run_id):
        self.run_id = run_id

    def process(self, record):
        source_file = record.pop('_source_file', 'unknown')

        # Validate
        validated_record, errors = validate_application_record(record)

        if not errors:
            # Valid record - enrich and output
            enriched = {
                'run_id': self.run_id,
                'processed_timestamp': datetime.utcnow().isoformat(),
                'source_file': source_file,
                **validated_record
            }
            yield enriched
        else:
            # Error record - output to errors
            for error in errors:
                yield beam.pvalue.TaggedOutput('validation_errors', {
                    'run_id': self.run_id,
                    'processed_timestamp': datetime.utcnow().isoformat(),
                    'source_file': source_file,
                    'application_id': record.get('application_id', ''),
                    'error_field': error.field,
                    'error_message': error.message,
                    'error_value': str(error.value)[:100],  # Truncate long values
                    'raw_record': json.dumps(record)
                })

# Pipeline options
options = PipelineOptions([
    '--runner=DirectRunner',
    f'--project={PROJECT_ID}',
    '--region=us-central1'
])

print("⚙️  Creating pipeline...")

# Build pipeline
with beam.Pipeline(options=options) as p:
    # Read files
    lines = (
        p
        | 'Read CSV Files' >> beam.io.ReadFromTextWithFilename(INPUT_PATTERN)
    )

    # Parse CSV
    parsed = (
        lines
        | 'Parse CSV' >> beam.ParDo(ParseCSV()).with_outputs('parse_errors', main='main')
    )

    # Validate and enrich
    validated = (
        parsed.main
        | 'Validate and Enrich' >> beam.ParDo(ValidateAndEnrich(RUN_ID)).with_outputs('validation_errors', main='main')
    )

    # Write valid records to BigQuery
    valid_output = (
        validated.main
        | 'Write to BigQuery' >> beam.io.WriteToBigQuery(
            OUTPUT_TABLE,
            schema=get_applications_raw_schema(),
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
        )
    )

    # Write errors to BigQuery
    error_output = (
        validated.validation_errors
        | 'Write Errors to BigQuery' >> beam.io.WriteToBigQuery(
            ERROR_TABLE,
            schema=get_applications_errors_schema(),
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
        )
    )

print("")
print("✅ Pipeline created and running...")
print("")

PIPELINE_SCRIPT

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                 ✅ PIPELINE TRIGGERED!                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Step 4: Show results
echo "📊 Step 4: Checking results..."
echo ""

sleep 5  # Give BigQuery a moment to update

echo "Valid Records:"
bq query --use_legacy_sql=false --format=pretty \
'SELECT COUNT(*) as total_valid FROM `loa-migration-dev.loa_migration.applications_raw`' 2>/dev/null || echo "  (Query pending...)"

echo ""
echo "Error Records:"
bq query --use_legacy_sql=false --format=pretty \
'SELECT COUNT(*) as total_errors FROM `loa-migration-dev.loa_migration.applications_errors`' 2>/dev/null || echo "  (Query pending...)"

echo ""
echo "🔗 View in BigQuery Console:"
echo "   https://console.cloud.google.com/bigquery?project=loa-migration-dev&d=loa_migration"
echo ""
echo "✅ DONE!"

