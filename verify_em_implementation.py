#!/usr/bin/env python3
"""
EM Implementation Verification Script
======================================

Run this script to verify the EM implementation is complete and working.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def check_imports():
    """Check all EM imports work."""
    results = []

    # 1. Config imports
    try:
        from deployments.em.config import (
            SYSTEM_ID, REQUIRED_ENTITIES, ODP_DATASET, FDP_DATASET,
            CUSTOMERS_HEADERS, ACCOUNTS_HEADERS, DECISION_HEADERS,
            ALLOWED_STATUSES, ALLOWED_ACCOUNT_TYPES, ALLOWED_DECISION_CODES,
            SCORE_MIN, SCORE_MAX
        )
        results.append(("Config imports", "PASS", f"SYSTEM_ID={SYSTEM_ID}"))
    except Exception as e:
        results.append(("Config imports", "FAIL", str(e)))

    # 2. Domain schema imports
    try:
        from deployments.em.domain.schema import (
            ODP_CUSTOMERS_SCHEMA, ODP_ACCOUNTS_SCHEMA, ODP_DECISION_SCHEMA,
            FDP_EM_ATTRIBUTES_SCHEMA, EM_SCHEMAS, get_schema
        )
        results.append(("Domain schema imports", "PASS", f"Entities: {list(EM_SCHEMAS.keys())}"))
    except Exception as e:
        results.append(("Domain schema imports", "FAIL", str(e)))

    # 3. Validation imports
    try:
        from deployments.em.validation import (
            ValidationResult, EMFileValidator, EMRecordValidator, EMValidator
        )
        results.append(("Validation imports", "PASS", "All validators available"))
    except Exception as e:
        results.append(("Validation imports", "FAIL", str(e)))

    # 4. Pipeline imports
    try:
        from deployments.em.pipeline.em_pipeline import (
            ValidateEMRecordDoFn, AddAuditColumnsDoFn, EM_ENTITY_CONFIG
        )
        results.append(("Pipeline imports", "PASS", f"Entities: {list(EM_ENTITY_CONFIG.keys())}"))
    except Exception as e:
        results.append(("Pipeline imports", "FAIL", str(e)))

    return results


def check_config_values():
    """Verify config values are correct."""
    results = []

    try:
        from deployments.em.config import (
            SYSTEM_ID, REQUIRED_ENTITIES, SCORE_MIN, SCORE_MAX
        )

        # Check SYSTEM_ID
        if SYSTEM_ID == "EM":
            results.append(("SYSTEM_ID == 'EM'", "PASS", ""))
        else:
            results.append(("SYSTEM_ID == 'EM'", "FAIL", f"Got: {SYSTEM_ID}"))

        # Check REQUIRED_ENTITIES
        if set(REQUIRED_ENTITIES) == {"customers", "accounts", "decision"}:
            results.append(("REQUIRED_ENTITIES", "PASS", ""))
        else:
            results.append(("REQUIRED_ENTITIES", "FAIL", f"Got: {REQUIRED_ENTITIES}"))

        # Check SCORE range
        if SCORE_MIN == 300 and SCORE_MAX == 850:
            results.append(("SCORE_RANGE (300-850)", "PASS", ""))
        else:
            results.append(("SCORE_RANGE", "FAIL", f"Got: {SCORE_MIN}-{SCORE_MAX}"))

    except Exception as e:
        results.append(("Config values", "FAIL", str(e)))

    return results


def check_schema_structure():
    """Verify schema structure."""
    results = []

    try:
        from deployments.em.domain.schema import get_schema, get_field_names

        # Check customers schema
        customers = get_schema('customers')
        customer_fields = [f['name'] for f in customers]
        if 'customer_id' in customer_fields and '_run_id' in customer_fields:
            results.append(("Customers schema", "PASS", f"{len(customers)} fields"))
        else:
            results.append(("Customers schema", "FAIL", "Missing fields"))

        # Check accounts schema
        accounts = get_schema('accounts')
        account_fields = [f['name'] for f in accounts]
        if 'account_id' in account_fields and 'customer_id' in account_fields:
            results.append(("Accounts schema", "PASS", f"{len(accounts)} fields"))
        else:
            results.append(("Accounts schema", "FAIL", "Missing fields"))

        # Check decision schema
        decision = get_schema('decision')
        decision_fields = [f['name'] for f in decision]
        if 'decision_id' in decision_fields and 'score' in decision_fields:
            results.append(("Decision schema", "PASS", f"{len(decision)} fields"))
        else:
            results.append(("Decision schema", "FAIL", "Missing fields"))

        # Check FDP schema
        fdp = get_schema('em_attributes')
        fdp_fields = [f['name'] for f in fdp]
        if 'attribute_key' in fdp_fields:
            results.append(("FDP em_attributes schema", "PASS", f"{len(fdp)} fields"))
        else:
            results.append(("FDP schema", "FAIL", "Missing attribute_key"))

    except Exception as e:
        results.append(("Schema structure", "FAIL", str(e)))

    return results


def check_file_structure():
    """Check that required files exist."""
    results = []
    base_path = os.path.join(project_root, "deployments", "em")

    required_files = [
        "config/__init__.py",
        "config/constants.py",
        "config/settings.py",
        "domain/__init__.py",
        "domain/schema.py",
        "validation/__init__.py",
        "validation/file_validator.py",
        "validation/record_validator.py",
        "validation/validator.py",
        "pipeline/__init__.py",
        "pipeline/em_pipeline.py",
        "tests/conftest.py",
        "tests/unit/config/test_config.py",
        "tests/unit/domain/test_schema.py",
        "tests/unit/pipeline/test_em_pipeline.py",
        "tests/unit/validation/test_validator.py",
        "transformations/dbt/dbt_project.yml",
        "transformations/dbt/models/staging/em/_em_sources.yml",
        "transformations/dbt/models/fdp/em_attributes.sql",
    ]

    for file_path in required_files:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            results.append((f"File: {file_path}", "PASS", ""))
        else:
            results.append((f"File: {file_path}", "FAIL", "Not found"))

    return results


def print_results(title, results):
    """Print results in a table format."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

    passed = 0
    failed = 0

    for name, status, details in results:
        if status == "PASS":
            passed += 1
            icon = "✅"
        else:
            failed += 1
            icon = "❌"

        if details:
            print(f"{icon} {name}: {status} - {details}")
        else:
            print(f"{icon} {name}: {status}")

    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print(" EM IMPLEMENTATION VERIFICATION")
    print("="*60)

    all_passed = True

    # Run checks
    all_passed &= print_results("1. IMPORT CHECKS", check_imports())
    all_passed &= print_results("2. CONFIG VALUES", check_config_values())
    all_passed &= print_results("3. SCHEMA STRUCTURE", check_schema_structure())
    all_passed &= print_results("4. FILE STRUCTURE", check_file_structure())

    print("\n" + "="*60)
    if all_passed:
        print(" ✅ ALL CHECKS PASSED - EM Implementation Complete")
    else:
        print(" ❌ SOME CHECKS FAILED - Review above for details")
    print("="*60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

