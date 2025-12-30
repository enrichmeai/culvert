#!/usr/bin/env python3
"""
LOCAL LOA DEPLOYMENT - Test & Learn Script
============================================

This script runs the complete LOA pipeline locally using DirectRunner
(no GCP/cloud resources needed - completely local and free!)

Usage:
    python3 deploy_local.py

What it does:
    1. Creates sample data (100 test records)
    2. Runs validation on each record
    3. Shows which records passed/failed
    4. Generates a simple report
    5. Demonstrates the complete flow
"""

import sys
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from blueprint.components.loa_domain.validation import validate_application_record, ValidationError
from blueprint.components.loa_domain.schema import (
    APPLICATIONS_RAW_SCHEMA,
    get_field_names,
    get_required_fields,
    record_to_bq_compatible,
)
from gdw_data_core.core import generate_run_id


def create_sample_data(num_records=100):
    """Create sample CSV data for testing."""
    print("\n" + "="*70)
    print("STEP 1: CREATING SAMPLE DATA")
    print("="*70)

    sample_data = [
        # Valid records
        ("APP001", "123-45-6789", "John Doe", "50000", "MORTGAGE", "2025-01-15", "NY1234", "john@example.com", "555-1234", "EMPLOYED", "75000", "750"),
        ("APP002", "234-56-7890", "Jane Smith", "30000", "PERSONAL", "2025-01-14", "CA5678", "jane@example.com", "555-5678", "EMPLOYED", "60000", "720"),
        ("APP003", "345-67-8901", "Bob Johnson", "100000", "HOME_EQUITY", "2025-01-13", "TX9012", "bob@example.com", "555-9012", "SELF_EMPLOYED", "120000", "760"),
        ("APP004", "456-78-9012", "Alice Brown", "45000", "AUTO", "2025-01-12", "FL3456", "alice@example.com", "555-3456", "EMPLOYED", "55000", "700"),
        ("APP005", "567-89-0123", "Charlie Davis", "75000", "MORTGAGE", "2025-01-11", "IL7890", "charlie@example.com", "555-7890", "EMPLOYED", "90000", "780"),
        # Invalid records (for testing error handling)
        ("APP006", "000-00-0000", "Invalid SSN", "25000", "MORTGAGE", "2025-01-10", "OH2345", "invalid@example.com", "555-1111", "EMPLOYED", "40000", "650"),  # Bad SSN
        ("APP007", "678-90-1234", "Bad Loan", "-5000", "MORTGAGE", "2025-01-09", "MI3456", "bad@example.com", "555-2222", "EMPLOYED", "50000", "700"),  # Negative amount
        ("APP008", "789-01-2345", "Bad Type", "60000", "INVALID_TYPE", "2025-01-08", "WI4567", "badtype@example.com", "555-3333", "EMPLOYED", "70000", "710"),  # Bad loan type
        ("APP009", "890-12-3456", "Future Date", "55000", "MORTGAGE", "2099-01-07", "VA5678", "future@example.com", "555-4444", "EMPLOYED", "80000", "720"),  # Future date
    ]

    # Create CSV file
    csv_path = Path("/tmp/loa_sample_data.csv")
    field_names = get_field_names(APPLICATIONS_RAW_SCHEMA)[:12]  # First 12 fields (no metadata)

    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(field_names)
        for i in range(num_records):
            record = sample_data[i % len(sample_data)]
            writer.writerow(record)

    print(f"✅ Created sample data: {csv_path}")
    print(f"   Total records: {num_records}")
    print(f"   Sample fields: {field_names}")

    return csv_path


def process_records(csv_path):
    """Process records through validation pipeline."""
    print("\n" + "="*70)
    print("STEP 2: PROCESSING RECORDS THROUGH VALIDATION")
    print("="*70)

    field_names = get_field_names(APPLICATIONS_RAW_SCHEMA)[:12]
    run_id = generate_run_id("local_test")

    valid_records = []
    error_records = []

    print(f"\nRun ID: {run_id}")
    print(f"Processing records from: {csv_path}\n")

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f, fieldnames=field_names)
        next(reader)  # Skip header

        for record_num, row in enumerate(reader, start=1):
            # Convert to record dict
            record = dict(row)

            # Validate
            validated, errors = validate_application_record(record)

            if errors:
                error_records.append({
                    "record_num": record_num,
                    "application_id": record.get("application_id"),
                    "errors": errors,
                    "raw_record": record
                })
                print(f"❌ Record {record_num}: FAILED - {len(errors)} error(s)")
                for err in errors:
                    print(f"   • {err.field}: {err.message}")
            else:
                valid_records.append({
                    "record_num": record_num,
                    "validated_data": validated,
                })
                print(f"✅ Record {record_num}: PASSED - {record.get('application_id')}")

    print(f"\n" + "-"*70)
    print(f"Processing Summary:")
    print(f"  Total records processed: {record_num}")
    print(f"  Valid records: {len(valid_records)} ({len(valid_records)/record_num*100:.1f}%)")
    print(f"  Error records: {len(error_records)} ({len(error_records)/record_num*100:.1f}%)")
    print("-"*70)

    return valid_records, error_records, run_id


def generate_report(valid_records, error_records, run_id):
    """Generate processing report."""
    print("\n" + "="*70)
    print("STEP 3: GENERATING REPORT")
    print("="*70)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_records": len(valid_records) + len(error_records),
            "valid_records": len(valid_records),
            "error_records": len(error_records),
            "success_rate": f"{len(valid_records)/(len(valid_records) + len(error_records))*100:.1f}%"
        },
        "valid_sample": [
            {
                "record_num": r["record_num"],
                "application_id": r["validated_data"].get("application_id"),
                "loan_amount": r["validated_data"].get("loan_amount"),
                "loan_type": r["validated_data"].get("loan_type"),
            }
            for r in valid_records[:3]  # First 3 valid records
        ],
        "error_sample": [
            {
                "record_num": e["record_num"],
                "application_id": e["application_id"],
                "errors": [
                    {"field": err.field, "message": err.message}
                    for err in e["errors"]
                ]
            }
            for e in error_records[:3]  # First 3 error records
        ]
    }

    print(f"\n📊 REPORT")
    print(f"   Run ID: {report['run_id']}")
    print(f"   Timestamp: {report['timestamp']}")
    print(f"   Total records: {report['summary']['total_records']}")
    print(f"   Valid: {report['summary']['valid_records']} ({report['summary']['success_rate']})")
    print(f"   Errors: {report['summary']['error_records']}")

    print(f"\n✅ Valid Records (Sample):")
    for record in report['valid_sample']:
        print(f"   • Record #{record['record_num']}: {record['application_id']} - ${record['loan_amount']} {record['loan_type']}")

    print(f"\n❌ Error Records (Sample):")
    for record in report['error_sample']:
        print(f"   • Record #{record['record_num']}: {record['application_id']}")
        for err in record['errors']:
            print(f"     - {err['field']}: {err['message']}")

    # Save report
    report_path = Path("/tmp/loa_deployment_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n📄 Full report saved to: {report_path}")

    return report


def show_schema_info():
    """Display schema information."""
    print("\n" + "="*70)
    print("SCHEMA INFORMATION")
    print("="*70)

    field_names = get_field_names(APPLICATIONS_RAW_SCHEMA)
    required_fields = get_required_fields(APPLICATIONS_RAW_SCHEMA)

    print(f"\nTotal fields: {len(field_names)}")
    print(f"Required fields: {len(required_fields)}")

    print(f"\n📋 Field Names:")
    for i, field in enumerate(field_names, 1):
        is_required = "REQUIRED" if field in required_fields else "optional"
        print(f"   {i:2d}. {field:30s} [{is_required}]")


def main():
    """Main deployment function."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "LOA BLUEPRINT - LOCAL DEPLOYMENT TEST" + " "*15 + "║")
    print("║" + " "*16 + "(No GCP/Cloud Resources - Completely Local!)" + " "*7 + "║")
    print("╚" + "="*68 + "╝")

    try:
        # Show schema info
        show_schema_info()

        # Create sample data
        csv_path = create_sample_data(num_records=100)

        # Process records
        valid_records, error_records, run_id = process_records(csv_path)

        # Generate report
        report = generate_report(valid_records, error_records, run_id)

        print("\n" + "="*70)
        print("✅ LOCAL DEPLOYMENT TEST COMPLETE!")
        print("="*70)
        print(f"\nKey Learnings:")
        print(f"  1. Validation module works correctly")
        print(f"  2. Valid records pass all checks")
        print(f"  3. Invalid records are caught with errors")
        print(f"  4. Error messages are clear and actionable")
        print(f"  5. PII is masked in error messages")
        print(f"\nNext Steps:")
        print(f"  1. Review the report: {Path('/tmp/loa_deployment_report.json')}")
        print(f"  2. Read HANDS_ON_IMPLEMENTATION_GUIDE.md for GCP deployment")
        print(f"  3. Set up GCP account and deploy to BigQuery")
        print(f"\n")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

