import os
import subprocess
import json
import pytest

def test_pii_macros_compilation():
    # Detect if we are running from project root or library root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Debug: Check if profiles.yml exists
    profiles_path = os.path.join(project_dir, "profiles.yml")
    print(f"DEBUG: project_dir={project_dir}")
    print(f"DEBUG: profiles_path={profiles_path}")
    print(f"DEBUG: profiles_exists={os.path.exists(profiles_path)}")
    if os.path.exists(profiles_path):
        with open(profiles_path, 'r') as f:
            print(f"DEBUG: profiles_content:\n{f.read()}")

    # Run dbt compile
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    result = subprocess.run(
        ["dbt", "compile", "--project-dir", project_dir, "--target", "dev", "--profiles-dir", project_dir],
        capture_output=True,
        text=True,
        env=env
    )

    assert result.returncode == 0, f"dbt compile failed: {result.stdout} {result.stderr}"

    # Check compiled SQL for test_pii_output
    compiled_path = os.path.join(project_dir, "target/compiled/transform_unit_tests/models/test_pii_output.sql")
    assert os.path.exists(compiled_path), "Compiled SQL file not found"

    with open(compiled_path, 'r') as f:
        compiled_sql = f.read().upper()

    # Verify ssn masking (CONCAT('XXX-XX-', SUBSTRING(CAST(ssn AS STRING), -4)))
    assert "'XXX-XX-'" in compiled_sql
    assert "SUBSTRING(CAST(SSN AS STRING), -4)" in compiled_sql

    # Verify ssn full masking (RPAD('', LENGTH(CAST(ssn AS STRING)), '*'))
    assert "RPAD('', LENGTH(CAST(SSN AS STRING)), '*')" in compiled_sql

    # Verify account masking (SUBSTRING(CAST(account_number AS STRING), -4))
    assert "SUBSTRING(CAST(ACCOUNT_NUMBER AS STRING), -4)" in compiled_sql

    # Verify email masking (CONCAT('****', SUBSTRING(CAST(email AS STRING), POSITION('@' IN CAST(email AS STRING)))))
    assert "'****'" in compiled_sql
    assert "SUBSTRING(CAST(EMAIL AS STRING), POSITION('@' IN CAST(EMAIL AS STRING)))" in compiled_sql

    # Verify phone masking (CONCAT(SUBSTRING(CAST(phone AS STRING), 1, 3), '-***-', SUBSTRING(CAST(phone AS STRING), -4)))
    assert "SUBSTRING(CAST(PHONE AS STRING), 1, 3)" in compiled_sql
    assert "'-***-'" in compiled_sql
    assert "SUBSTRING(CAST(PHONE AS STRING), -4)" in compiled_sql

    # Verify name masking (SUBSTRING(CAST(first_name AS STRING), 1, 1))
    assert "SUBSTRING(CAST(FIRST_NAME AS STRING), 1, 1)" in compiled_sql
    assert "RPAD('', LENGTH(CAST(FIRST_NAME AS STRING)) - 1, '*')" in compiled_sql

def test_audit_macros_compilation():
    # Detect if we are running from project root or library root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Run dbt compile
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    subprocess.run(
        ["dbt", "compile", "--project-dir", project_dir, "--target", "dev", "--profiles-dir", project_dir],
        capture_output=True,
        text=True,
        env=env
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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Run dbt compile
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    subprocess.run(
        ["dbt", "compile", "--project-dir", project_dir, "--target", "dev", "--profiles-dir", project_dir],
        capture_output=True,
        text=True,
        env=env
    )

    # Check compiled SQL for test_dq_output
    compiled_path = os.path.join(project_dir, "target/compiled/transform_unit_tests/models/test_dq_output.sql")
    assert os.path.exists(compiled_path), "Compiled SQL file for DQ not found"

    with open(compiled_path, 'r') as f:
        compiled_sql = f.read().upper()

    # Verify DQ macro logic in SQL
    assert "WHERE SSN IS NULL" in compiled_sql
    assert "SELECT COUNT(DISTINCT SSN)" in compiled_sql

def test_enrichment_macros_compilation():
    # Detect if we are running from project root or library root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Run dbt compile
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    subprocess.run(
        ["dbt", "compile", "--project-dir", project_dir, "--target", "dev", "--profiles-dir", project_dir],
        capture_output=True,
        text=True,
        env=env
    )

    # Check compiled SQL for test_enrichment_output
    compiled_path = os.path.join(project_dir, "target/compiled/transform_unit_tests/models/test_enrichment_output.sql")
    assert os.path.exists(compiled_path), "Compiled SQL file for enrichment not found"

    with open(compiled_path, 'r') as f:
        compiled_sql = f.read().upper()

    # Verify date enrichment
    assert "EXTRACT(YEAR FROM APPLICATION_DATE) AS APP_YEAR" in compiled_sql
    assert "FORMAT_DATE('%A', APPLICATION_DATE) AS APP_DAY_NAME" in compiled_sql

    # Verify bucketing enrichment
    assert "WHEN LOAN_AMOUNT <100000 THEN 'SMALL'" in compiled_sql
    assert "WHEN LOAN_AMOUNT BETWEEN 100000 AND 500000 THEN 'MEDIUM'" in compiled_sql
    assert "END AS AMOUNT_CATEGORY" in compiled_sql

    # Verify lookup enrichment
    assert "CASE STATUS" in compiled_sql
    assert "WHEN 'A' THEN 'ACTIVE'" in compiled_sql
    assert "END AS STATUS_DESC" in compiled_sql

    # Verify expression enrichment
    assert "CASE WHEN CREDIT_SCORE >= 700 THEN \"GOOD\" ELSE \"BAD\" END AS CREDIT_QUALITY" in compiled_sql

if __name__ == "__main__":
    test_pii_macros_compilation()
    test_audit_macros_compilation()
    test_dq_macros_compilation()
    test_enrichment_macros_compilation()
