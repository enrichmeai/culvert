#!/usr/bin/env python3
"""
Generate LOA Output Data Files
Demonstrates complete data flow with input → validation → output

This script:
1. Reads from data/input/
2. Validates records
3. Outputs to data/output/ (valid and failed separately)
"""

import csv
from datetime import datetime
from pathlib import Path

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*70)
print("LOA PIPELINE - GENERATE OUTPUT FILES")
print("="*70)
print()

# ============================================================================
# VALIDATION RULES
# ============================================================================

def validate_ssn(ssn):
    """Validate SSN format"""
    if not ssn or len(ssn) != 11:
        return False, "SSN must be XXX-XX-XXXX format"
    if ssn == "000-00-0000":
        return False, "SSN cannot be all zeros"
    return True, None

def validate_amount(amount):
    """Validate loan amount"""
    try:
        amt = float(amount)
        if amt <= 0:
            return False, "Amount must be positive"
        if amt > 1000000:
            return False, "Amount exceeds maximum"
        return True, None
    except:
        return False, "Amount must be numeric"

def validate_loan_type(loan_type):
    """Validate loan type"""
    valid_types = ["MORTGAGE", "PERSONAL", "AUTO", "HOME_EQUITY"]
    if loan_type not in valid_types:
        return False, f"Type must be one of: {', '.join(valid_types)}"
    return True, None

def validate_date(date_str):
    """Validate date"""
    try:
        from datetime import datetime
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        if date_obj > datetime.now():
            return False, "Cannot be future date"
        return True, None
    except:
        return False, "Invalid date format"

# ============================================================================
# PROCESS CUSTOMERS DATA
# ============================================================================

print("📖 Reading customers_20250120.csv...")
valid_customers = []
failed_customers = []

customers_file = INPUT_DIR / "customers_20250120.csv"

if customers_file.exists():
    with open(customers_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            errors = []

            # Validate fields
            if 'customer_id' not in row or not row['customer_id']:
                errors.append("Missing customer_id")

            # Add to appropriate list
            if errors:
                failed_customers.append({**row, "errors": "; ".join(errors)})
            else:
                valid_customers.append(row)

    print(f"✅ Read {len(valid_customers)} valid, {len(failed_customers)} failed")
else:
    print(f"⚠️  File not found: {customers_file}")
    # Create sample data
    valid_customers = [
        {"customer_id": "CUST001", "name": "John Doe", "email": "john@example.com"},
        {"customer_id": "CUST002", "name": "Jane Smith", "email": "jane@example.com"},
    ]
    failed_customers = [
        {"customer_id": "", "name": "No ID", "email": "noid@example.com", "errors": "Missing customer_id"},
    ]

# Write valid customers
customers_valid_file = OUTPUT_DIR / "customers_processed.csv"
if valid_customers:
    with open(customers_valid_file, 'w', newline='') as f:
        fieldnames = list(valid_customers[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_customers)
    print(f"✅ Output: {customers_valid_file}")
    print(f"   Records: {len(valid_customers)}")

# Write failed customers
customers_failed_file = OUTPUT_DIR / "customers_errors.csv"
if failed_customers:
    with open(customers_failed_file, 'w', newline='') as f:
        fieldnames = list(failed_customers[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(failed_customers)
    print(f"❌ Output: {customers_failed_file}")
    print(f"   Records: {len(failed_customers)}")

# ============================================================================
# PROCESS APPLICATIONS DATA
# ============================================================================

print()
print("📖 Generating applications output (simulated)...")

# Create sample application records
applications_data = [
    {"app_id": "APP001", "ssn": "123-45-6789", "name": "John Doe", "amount": "50000", "loan_type": "MORTGAGE", "date": "2025-01-15"},
    {"app_id": "APP002", "ssn": "234-56-7890", "name": "Jane Smith", "amount": "30000", "loan_type": "PERSONAL", "date": "2025-01-14"},
    {"app_id": "APP003", "ssn": "345-67-8901", "name": "Bob Johnson", "amount": "75000", "loan_type": "HOME_EQUITY", "date": "2025-01-13"},
    {"app_id": "APP004", "ssn": "000-00-0000", "name": "Bad SSN", "amount": "50000", "loan_type": "MORTGAGE", "date": "2025-01-12"},
    {"app_id": "APP005", "ssn": "456-78-9012", "name": "Negative Amt", "amount": "-5000", "loan_type": "PERSONAL", "date": "2025-01-11"},
    {"app_id": "APP006", "ssn": "567-89-0123", "name": "Bad Type", "amount": "60000", "loan_type": "INVALID", "date": "2025-01-10"},
]

valid_apps = []
failed_apps = []

for app in applications_data:
    errors = []

    # Validate SSN
    valid, msg = validate_ssn(app["ssn"])
    if not valid:
        errors.append(msg)

    # Validate amount
    valid, msg = validate_amount(app["amount"])
    if not valid:
        errors.append(msg)

    # Validate loan type
    valid, msg = validate_loan_type(app["loan_type"])
    if not valid:
        errors.append(msg)

    # Validate date
    valid, msg = validate_date(app["date"])
    if not valid:
        errors.append(msg)

    if errors:
        failed_apps.append({**app, "errors": "; ".join(errors), "error_timestamp": datetime.now().isoformat()})
    else:
        valid_apps.append({**app, "processed_timestamp": datetime.now().isoformat()})

# Write valid applications
apps_valid_file = OUTPUT_DIR / "applications_processed.csv"
if valid_apps:
    with open(apps_valid_file, 'w', newline='') as f:
        fieldnames = ["app_id", "ssn", "name", "amount", "loan_type", "date", "processed_timestamp"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_apps)
    print(f"✅ Output: {apps_valid_file}")
    print(f"   Records: {len(valid_apps)}")
else:
    # Create empty file
    with open(apps_valid_file, 'w', newline='') as f:
        f.write("app_id,ssn,name,amount,loan_type,date,processed_timestamp\n")
    print(f"✅ Output: {apps_valid_file} (header only)")

# Write failed applications
apps_failed_file = OUTPUT_DIR / "applications_errors.csv"
if failed_apps:
    with open(apps_failed_file, 'w', newline='') as f:
        fieldnames = ["app_id", "ssn", "name", "amount", "loan_type", "date", "errors", "error_timestamp"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(failed_apps)
    print(f"❌ Output: {apps_failed_file}")
    print(f"   Records: {len(failed_apps)}")
else:
    print(f"❌ No failed applications")

# ============================================================================
# SUMMARY
# ============================================================================

print()
print("="*70)
print("SUMMARY")
print("="*70)
print()
print("📁 OUTPUT FILES GENERATED:")
print()
print("✅ VALID DATA (Ready for BigQuery):")
print(f"   {customers_valid_file}")
print(f"   {apps_valid_file}")
print()
print("❌ FAILED DATA (Requires Investigation):")
print(f"   {customers_failed_file}")
print(f"   {apps_failed_file}")
print()
print("📊 DATA FLOW:")
print()
print("   Input → Validation → Split")
print("   ├─→ Valid → *_processed.csv")
print("   └─→ Failed → *_errors.csv")
print()
print("="*70)
print("✅ OUTPUT FILES GENERATION COMPLETE!")
print("="*70)

