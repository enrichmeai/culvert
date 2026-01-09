import os
import subprocess
import json
import pytest

def test_pii_macros_compilation():
    # Detect if we are running from project root or library root
    if os.path.exists("libraries/gcp-pipeline-transform/tests/unit/dbt_test_project"):
        project_dir = "libraries/gcp-pipeline-transform/tests/unit/dbt_test_project"
    else:
        project_dir = "tests/unit/dbt_test_project"

    # Run dbt compile
    result = subprocess.run(
        ["dbt", "compile", "--project-dir", project_dir, "--profiles-dir", project_dir, "--target", "dev"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"dbt compile failed: {result.stdout} {result.stderr}"

    # Check compiled SQL for test_pii_output
    compiled_path = os.path.join(project_dir, "target/compiled/transform_unit_tests/models/test_pii_output.sql")
    assert os.path.exists(compiled_path), "Compiled SQL file not found"

    with open(compiled_path, 'r') as f:
        compiled_sql = f.read().upper()

    # Verify ssn masking (CONCAT(SUBSTRING(ssn, 1, 5), '-', SUBSTRING(ssn, -4)))
    assert "SUBSTRING(SSN, 1, 5)" in compiled_sql
    assert "'-'" in compiled_sql
    assert "SUBSTRING(SSN, -4)" in compiled_sql

    # Verify ssn full masking ('XXX-XX-XXXX')
    assert "'XXX-XX-XXXX'" in compiled_sql

    # Verify account masking (CONCAT(RPAD('*', LENGTH(account_number) - 4, '*'), SUBSTRING(account_number, -4)))
    assert "RPAD('*', LENGTH(ACCOUNT_NUMBER) - 4, '*')" in compiled_sql
    assert "SUBSTRING(ACCOUNT_NUMBER, -4)" in compiled_sql

    # Verify email masking (CONCAT('****', SUBSTRING(email, POSITION('@' IN email))))
    assert "'****'" in compiled_sql
    assert "SUBSTRING(EMAIL, POSITION('@' IN EMAIL))" in compiled_sql

    # Verify phone masking (CONCAT(SUBSTRING(phone, 1, 3), '-***-', SUBSTRING(phone, -4)))
    assert "SUBSTRING(PHONE, 1, 3)" in compiled_sql
    assert "'-***-'" in compiled_sql
    assert "SUBSTRING(PHONE, -4)" in compiled_sql

    # Verify name masking (CONCAT(SUBSTRING(first_name, 1, 1), '****', ' ', last_name))
    assert "SUBSTRING(FIRST_NAME, 1, 1)" in compiled_sql
    assert "'****'" in compiled_sql
    assert "' '" in compiled_sql
    assert "LAST_NAME" in compiled_sql

def test_audit_macros_compilation():
    # Detect if we are running from project root or library root
    if os.path.exists("libraries/gcp-pipeline-transform/tests/unit/dbt_test_project"):
        project_dir = "libraries/gcp-pipeline-transform/tests/unit/dbt_test_project"
    else:
        project_dir = "tests/unit/dbt_test_project"
    
    # Run dbt compile
    subprocess.run(
        ["dbt", "compile", "--project-dir", project_dir, "--profiles-dir", project_dir, "--target", "dev"],
        capture_output=True,
        text=True
    )

    # Check compiled SQL for test_audit_output
    compiled_path = os.path.join(project_dir, "target/compiled/transform_unit_tests/models/test_audit_output.sql")
    assert os.path.exists(compiled_path), "Compiled SQL file for audit not found"

    with open(compiled_path, 'r') as f:
        compiled_sql = f.read().upper()

    # Verify audit columns (, 'test_run_123' as run_id, current_timestamp() as processed_timestamp, 'test_file.csv' as source_file)
    assert "'TEST_RUN_123' AS RUN_ID" in compiled_sql
    assert "CURRENT_TIMESTAMP() AS PROCESSED_TIMESTAMP" in compiled_sql
    assert "'TEST_FILE.CSV' AS SOURCE_FILE" in compiled_sql

def test_dq_macros_compilation():
    # Detect if we are running from project root or library root
    if os.path.exists("libraries/gcp-pipeline-transform/tests/unit/dbt_test_project"):
        project_dir = "libraries/gcp-pipeline-transform/tests/unit/dbt_test_project"
    else:
        project_dir = "tests/unit/dbt_test_project"
    
    # Run dbt compile
    subprocess.run(
        ["dbt", "compile", "--project-dir", project_dir, "--profiles-dir", project_dir, "--target", "dev"],
        capture_output=True,
        text=True
    )

    # Check compiled SQL for test_dq_output
    compiled_path = os.path.join(project_dir, "target/compiled/transform_unit_tests/models/test_dq_output.sql")
    assert os.path.exists(compiled_path), "Compiled SQL file for DQ not found"

    with open(compiled_path, 'r') as f:
        compiled_sql = f.read().upper()

    # Verify DQ macro logic in SQL
    assert "WHERE SSN IS NULL" in compiled_sql
    assert "SELECT COUNT(DISTINCT SSN)" in compiled_sql

if __name__ == "__main__":
    test_pii_macros_compilation()
    test_audit_macros_compilation()
    test_dq_macros_compilation()
