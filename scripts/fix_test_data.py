#!/usr/bin/env python3
"""
Fix test data files and upload to GCS with correct HDR|TRL format.

Usage:
    python3 scripts/fix_test_data.py
"""

import os
import subprocess
import tempfile

EXTRACT_DATE = "20260319"
LANDING_BUCKET = "gs://joseph-antony-aruja-generic-int-landing"
ENTITIES = ["customers", "accounts", "decision", "applications"]

# Build content for each entity
def get_content(entity):
    data = {
        "customers": [
            f"HDR|GENERIC|CUSTOMERS|{EXTRACT_DATE}",
            "customer_id,first_name,last_name,ssn,dob,status,created_date",
            "CUST001,John,Doe,123-45-6789,1980-01-15,A,2020-03-01",
            "CUST002,Jane,Smith,987-65-4321,1985-05-20,A,2021-06-15",
            "TRL|RecordCount=2|Checksum=0a884d6658b60eaad5e69bf1bbcbb891",
        ],
        "accounts": [
            f"HDR|GENERIC|ACCOUNTS|{EXTRACT_DATE}",
            "account_id,customer_id,account_type,balance,status,open_date",
            "ACC001,CUST001,CHECKING,1000.00,A,2020-01-01",
            "ACC002,CUST002,SAVINGS,5000.00,A,2021-02-01",
            "TRL|RecordCount=2|Checksum=6dffa9dfa435b47ceeb2b6cac459156a",
        ],
        "decision": [
            f"HDR|GENERIC|DECISION|{EXTRACT_DATE}",
            "decision_id,customer_id,application_id,decision_code,decision_date,score,reason_codes",
            "DEC001,CUST001,APP001,APPROVE,2026-01-15T10:00:00,750,R001",
            "DEC002,CUST002,APP002,APPROVE,2026-01-20T11:00:00,800,R002",
            "TRL|RecordCount=2|Checksum=5ba9be86dfd174954fcb5da9c1b7b1e6",
        ],
        "applications": [
            f"HDR|GENERIC|APPLICATIONS|{EXTRACT_DATE}",
            "application_id,customer_id,loan_amount,interest_rate,term_months,application_date,status,event_type,account_type",
            "APP001,CUST001,25000.00,5.5,60,2025-01-10,APPROVED,NEW_APPLICATION,PORTFOLIO",
            "APP002,CUST002,15000.00,6.0,36,2025-02-15,PENDING,NEW_APPLICATION,EXCESS",
            "TRL|RecordCount=2|Checksum=0a884d6658b60eaad5e69bf1bbcbb891",
        ],
    }
    return "\n".join(data[entity]) + "\n"


def main():
    print("=" * 60)
    print("Creating and uploading test files")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for entity in ENTITIES:
            content = get_content(entity)
            
            # Write CSV
            csv_path = os.path.join(tmpdir, f"generic_{entity}_{EXTRACT_DATE}.csv")
            with open(csv_path, 'w') as f:
                f.write(content)
            
            # Write OK trigger
            ok_path = os.path.join(tmpdir, f"generic_{entity}_{EXTRACT_DATE}.ok")
            with open(ok_path, 'w') as f:
                f.write("OK\n")
            
            # Verify pipes
            with open(csv_path, 'rb') as f:
                first_bytes = f.read(60)
                has_pipes = b'|' in first_bytes
            
            print(f"\n{entity}:")
            print(f"  Has pipes: {has_pipes}")
            print(f"  First bytes: {first_bytes[:50]}")
            
            # Upload to GCS
            gcs_csv = f"{LANDING_BUCKET}/generic/{entity}/generic_{entity}_{EXTRACT_DATE}.csv"
            gcs_ok = f"{LANDING_BUCKET}/generic/{entity}/generic_{entity}_{EXTRACT_DATE}.ok"
            
            subprocess.run(["gsutil", "cp", csv_path, gcs_csv], check=True)
            subprocess.run(["gsutil", "cp", ok_path, gcs_ok], check=True)
            print(f"  Uploaded to GCS")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()

