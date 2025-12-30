"""
PyTest Configuration and Fixtures for LOA Blueprint Tests
==========================================================

Provides centralized fixtures for:
- Test data generation (CSV with valid/invalid loan application records)
- Temporary output directories for pipeline results
- BigQuery client mocking for unit tests
- Sample Airflow DAG instantiation for DAG testing

All fixtures include proper cleanup and documentation.

Usage:
    pytest tests/ -v
    pytest tests/unit/ -v
    pytest tests/integration/ -v

Scope:
    - session: Single instance for entire test session
    - function: New instance for each test function
"""

import csv
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Generator
from unittest.mock import MagicMock

import pytest

try:
    from faker import Faker as FakerClass
except ImportError:
    FakerClass = None  # type: ignore # Will be skipped if faker not installed


# ============================================================================
# SAMPLE CSV DATA FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def sample_csv_data() -> Generator[str, None, None]:
    """
    Create a temporary CSV file with test loan application data.

    Creates a CSV file containing both valid and invalid application records
    for testing the LOA pipeline. The file includes:
    - Valid records with complete, correct data
    - Invalid records with missing/malformed fields
    - Records with boundary value test cases

    The CSV follows the LOA schema:
    - run_id: Unique run identifier
    - processed_timestamp: ISO timestamp
    - source_file: Original source file name
    - application_id: Unique application ID
    - ssn: Social Security Number
    - applicant_name: Full applicant name
    - loan_amount: Loan amount in dollars
    - loan_type: MORTGAGE, PERSONAL, AUTO, or HOME_EQUITY
    - application_date: YYYY-MM-DD format
    - branch_code: Processing branch identifier

    Cleanup:
        Temporary file is automatically deleted after test completion.

    Returns:
        str: Path to the temporary CSV file

    Example:
        def test_pipeline_with_sample_data(sample_csv_data):
            with open(sample_csv_data, 'r') as f:
                reader = csv.DictReader(f)
                records = list(reader)
                assert len(records) > 0
    """
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.csv',
        delete=False,
        newline=''
    )

    try:
        # Prepare test data with valid and invalid records
        test_records = _generate_test_records()

        # Write CSV header
        fieldnames = [
            'run_id', 'processed_timestamp', 'source_file', 'application_id',
            'ssn', 'applicant_name', 'loan_amount', 'loan_type',
            'application_date', 'branch_code', 'applicant_email', 'applicant_phone'
        ]

        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()

        # Write test records
        for record in test_records:
            writer.writerow(record)

        temp_file.close()
        yield temp_file.name

    finally:
        # Cleanup: Remove temporary file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


def _generate_test_records() -> List[Dict[str, Any]]:
    """
    Generate test records for CSV data fixture.

    Returns a mix of valid and invalid records for comprehensive testing.

    Returns:
        List of dictionaries representing application records
    """
    if FakerClass is None:
        pytest.skip("Faker package not installed")

    faker_instance = FakerClass()
    FakerClass.seed(42)  # For reproducibility

    records = []
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    base_date = datetime.now()
    source_file = 'APP_EXTRACT_20250101.txt'
    phone_pattern = '##########'

    # Valid records
    for i in range(5):
        records.append({
            'run_id': run_id,
            'processed_timestamp': base_date.isoformat() + 'Z',
            'source_file': source_file,
            'application_id': f'APP{1000000 + i}',
            'ssn': f'{100 + i}-45-{6789 + i}',
            'applicant_name': faker_instance.name(),
            'loan_amount': 250000 + (i * 50000),
            'loan_type': ['MORTGAGE', 'PERSONAL', 'AUTO', 'HOME_EQUITY'][i % 4],
            'application_date': (base_date - timedelta(days=i)).strftime('%Y-%m-%d'),
            'branch_code': f'BRANCH{i % 5:03d}',
            'applicant_email': faker_instance.email(),
            'applicant_phone': '+44' + str(faker_instance.numerify(phone_pattern)),
        })

    # Invalid records - missing required field
    records.append({
        'run_id': run_id,
        'processed_timestamp': base_date.isoformat() + 'Z',
        'source_file': source_file,
        'application_id': '',  # Missing application_id
        'ssn': '123-45-6789',
        'applicant_name': faker_instance.name(),
        'loan_amount': 300000,
        'loan_type': 'MORTGAGE',
        'application_date': base_date.strftime('%Y-%m-%d'),
        'branch_code': 'BRANCH001',
        'applicant_email': faker_instance.email(),
        'applicant_phone': '+44' + str(faker_instance.numerify(phone_pattern)),
    })

    # Invalid records - malformed SSN (all zeros)
    records.append({
        'run_id': run_id,
        'processed_timestamp': base_date.isoformat() + 'Z',
        'source_file': source_file,
        'application_id': 'APP2000001',
        'ssn': '000-00-0000',  # Invalid: all zeros
        'applicant_name': faker_instance.name(),
        'loan_amount': 150000,
        'loan_type': 'PERSONAL',
        'application_date': base_date.strftime('%Y-%m-%d'),
        'branch_code': 'BRANCH002',
        'applicant_email': faker_instance.email(),
        'applicant_phone': '+44' + str(faker_instance.numerify(phone_pattern)),
    })

    # Invalid records - malformed loan amount
    records.append({
        'run_id': run_id,
        'processed_timestamp': base_date.isoformat() + 'Z',
        'source_file': source_file,
        'application_id': 'APP2000002',
        'ssn': '222-33-4444',
        'applicant_name': faker_instance.name(),
        'loan_amount': 'not_a_number',  # Invalid: not numeric
        'loan_type': 'AUTO',
        'application_date': base_date.strftime('%Y-%m-%d'),
        'branch_code': 'BRANCH003',
        'applicant_email': faker_instance.email(),
        'applicant_phone': '+44' + str(faker_instance.numerify(phone_pattern)),
    })

    # Invalid records - invalid loan type
    records.append({
        'run_id': run_id,
        'processed_timestamp': base_date.isoformat() + 'Z',
        'source_file': source_file,
        'application_id': 'APP2000003',
        'ssn': '333-45-6789',
        'applicant_name': faker_instance.name(),
        'loan_amount': 200000,
        'loan_type': 'INVALID_TYPE',  # Invalid: not in allowed types
        'application_date': base_date.strftime('%Y-%m-%d'),
        'branch_code': 'BRANCH004',
        'applicant_email': faker_instance.email(),
        'applicant_phone': '+44' + str(faker_instance.numerify(phone_pattern)),
    })

    # Invalid records - malformed date
    records.append({
        'run_id': run_id,
        'processed_timestamp': base_date.isoformat() + 'Z',
        'source_file': source_file,
        'application_id': 'APP2000004',
        'ssn': '444-55-6666',
        'applicant_name': faker_instance.name(),
        'loan_amount': 350000,
        'loan_type': 'HOME_EQUITY',
        'application_date': '2025-13-45',  # Invalid: invalid date format
        'branch_code': 'BRANCH005',
        'applicant_email': faker_instance.email(),
        'applicant_phone': '+44' + str(faker_instance.numerify(phone_pattern)),
    })

    return records


# ============================================================================
# TEMPORARY OUTPUT DIRECTORY FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def temp_output_dir() -> Generator[str, None, None]:
    """
    Create a temporary directory for pipeline output files.

    Provides an isolated temporary directory for tests that need to write
    output files (e.g., processed CSV files, JSON reports, etc.).

    The directory is automatically created and cleaned up after test completion.

    Cleanup:
        Directory and all contents are recursively deleted after test.

    Returns:
        str: Path to the temporary directory

    Example:
        def test_pipeline_output(temp_output_dir):
            output_file = os.path.join(temp_output_dir, 'results.json')
            # Write test output
            with open(output_file, 'w') as f:
                json.dump({'status': 'success'}, f)
            # File is automatically cleaned up
    """
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix='loa_pipeline_test_')

    try:
        yield temp_dir
    finally:
        # Cleanup: Remove temporary directory and all contents
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


# ============================================================================
# MOCK BIGQUERY CLIENT FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def mock_bigquery() -> MagicMock:
    """
    Create a mock BigQuery client for unit testing.

    Returns a fully mocked BigQuery client with the following methods:
    - load_table_from_file: Mocked to return a LoadJob
    - get_table: Mocked to return table metadata
    - insert_rows_json: Mocked to return insert results
    - query: Mocked to return query results
    - list_tables: Mocked to return table list

    The mock is configured with default return values and can be customized
    for specific test cases using standard unittest.mock patterns.

    Returns:
        MagicMock: Mocked BigQuery Client instance

    Example:
        def test_load_to_bigquery(mock_bigquery):
            # Mock is configured with default behavior
            mock_bigquery.load_table_from_file.return_value.job_id = 'test_job_123'

            # Use mock in test
            job = mock_bigquery.load_table_from_file(None, None)
            assert job.job_id == 'test_job_123'

        def test_insert_rows(mock_bigquery):
            # Configure mock for specific test
            mock_bigquery.insert_rows_json.return_value = ([], [])  # No errors

            errors = mock_bigquery.insert_rows_json('table', [])
            assert errors == []
    """
    # Create mock client
    mock_client = MagicMock()

    # Mock load_table_from_file method
    mock_load_job = MagicMock()
    mock_load_job.job_id = 'test_load_job_20250121_001'
    mock_load_job.state = 'DONE'
    mock_load_job.result.return_value = MagicMock()
    mock_client.load_table_from_file.return_value = mock_load_job

    # Mock get_table method
    mock_table = MagicMock()
    mock_table.num_rows = 1000
    mock_table.num_bytes = 512000
    mock_table.schema = [
        MagicMock(name='application_id', field_type='STRING'),
        MagicMock(name='ssn', field_type='STRING'),
        MagicMock(name='loan_amount', field_type='INTEGER'),
    ]
    mock_client.get_table.return_value = mock_table

    # Mock insert_rows_json method
    mock_client.insert_rows_json.return_value = []  # No errors

    # Mock query method
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = []
    mock_client.query.return_value = mock_query_job

    # Mock list_tables method
    mock_client.list_tables.return_value = []

    return mock_client


# ============================================================================
# SAMPLE AIRFLOW DAG FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def sample_dag():
    """
    Create a sample Airflow DAG for testing DAG structure and tasks.

    Creates a DAG using the create_loa_dag() factory function with
    standard test parameters. The DAG is suitable for testing:
    - DAG structure and dependencies
    - Task configuration and operators
    - DAG scheduling and retry logic
    - Task group organization

    Configuration:
        job_name: 'test_applications'
        input_pattern: 'gs://test-bucket/input/applications_*'
        output_table: 'test-project:loa_test.applications'
        error_table: 'test-project:loa_test.applications_errors'
        schedule_interval: '0 6 * * *' (Daily at 6 AM)
        project_id: 'test-project'
        region: 'europe-west2'

    Returns:
        DAG: Configured Airflow DAG instance

    Example:
        def test_dag_structure(sample_dag):
            # Test DAG properties
            assert sample_dag.dag_id == 'loa_test_applications'
            assert len(sample_dag.tasks) > 0

        def test_dag_tasks(sample_dag):
            # Get specific task
            task_ids = [task.task_id for task in sample_dag.tasks]
            assert 'wait_for_input' in task_ids
            assert 'run_dataflow_pipeline' in task_ids
    """
    # Import here to avoid circular dependencies and to only require DAG module
    # when this fixture is actually used
    try:
        from blueprint.components.loa_pipelines.dag_template import create_loa_dag

        # Create sample DAG with test parameters
        dag = create_loa_dag(
            job_name='test_applications',
            input_pattern='gs://test-bucket/input/applications_*',
            output_table='test-project:loa_test.applications',
            error_table='test-project:loa_test.applications_errors',
            schedule_interval='0 6 * * *',
            project_id='test-project',
            region='europe-west2',
            dataflow_template='gs://test-bucket/templates/loa_pipeline',
            temp_location='gs://test-bucket/temp',
        )
        return dag
    except ImportError as e:
        pytest.skip(f"loa_pipelines module not available: {str(e)}")


# ============================================================================
# FIXTURE UTILITIES AND HELPERS
# ============================================================================

@pytest.fixture(scope="session")
def faker_instance():
    """
    Provide a Faker instance with fixed seed for reproducibility.

    Session-scoped fixture that provides a single Faker instance
    throughout the entire test session.

    Returns:
        Faker: Faker instance with seed=42 for reproducibility

    Example:
        def test_with_faker(faker_instance):
            name = faker_instance.name()
            email = faker_instance.email()
    """
    if FakerClass is None:
        pytest.skip("Faker package not installed")

    faker = FakerClass()
    FakerClass.seed(42)
    return faker


@pytest.fixture(scope="function")
def isolated_filesystem(tmp_path) -> Path:
    """
    Provide an isolated temporary filesystem for tests.

    Function-scoped fixture that provides a clean temporary directory
    for each test. Uses pytest's tmp_path fixture under the hood.

    Returns:
        Path: Path object pointing to the temporary directory

    Example:
        def test_file_operations(isolated_filesystem):
            test_file = isolated_filesystem / 'test.txt'
            test_file.write_text('content')
            assert test_file.read_text() == 'content'
    """
    return tmp_path


# ============================================================================
# PYTEST CONFIGURATION HOOKS
# ============================================================================

def pytest_configure(config):
    """
    Configure pytest with custom markers and settings.

    Called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_gcp: mark test as requiring GCP credentials"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers based on test paths.

    Automatically adds markers to tests based on their location:
    - tests/unit/ -> @pytest.mark.unit
    - tests/integration/ -> @pytest.mark.integration
    """
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


# ============================================================================
# FIXTURE SUMMARY AND DOCUMENTATION
# ============================================================================

"""
CONFTEST FIXTURES SUMMARY
==========================

1. sample_csv_data (function-scoped)
   - Creates temporary CSV with test loan application data
   - Includes 5 valid records and 5 invalid records with various error types
   - Automatically cleans up temporary file after test
   - Returns: str (path to CSV file)

2. temp_output_dir (function-scoped)
   - Creates isolated temporary directory for test output
   - Useful for pipeline output, reports, and intermediate files
   - Automatically cleans up directory and all contents after test
   - Returns: str (path to directory)

3. mock_bigquery (function-scoped)
   - Provides fully mocked BigQuery client
   - Pre-configured with sensible defaults for common methods
   - Can be further customized using standard unittest.mock patterns
   - Returns: MagicMock (mocked BigQuery Client)

4. sample_dag (function-scoped)
   - Creates sample Airflow DAG for testing
   - Uses create_loa_dag() factory with standard test parameters
   - Suitable for DAG structure and task configuration tests
   - Returns: DAG (Airflow DAG instance)

5. faker_instance (session-scoped)
   - Provides reusable Faker instance with fixed seed
   - Ensures reproducible fake data across test session
   - Returns: Faker instance

6. isolated_filesystem (function-scoped)
   - Provides clean temporary directory using pytest's tmp_path
   - Useful for file I/O operations in tests
   - Returns: Path (pathlib.Path object)

USAGE PATTERNS
==============

# Multiple fixtures in one test
def test_pipeline_integration(sample_csv_data, temp_output_dir, mock_bigquery):
    with open(sample_csv_data) as f:
        records = csv.DictReader(f)
        # Process records
        mock_bigquery.insert_rows_json('table', records)

# Fixture composition
def test_with_faker(faker_instance):
    name = faker_instance.name()
    email = faker_instance.email()

# File operations
def test_file_handling(isolated_filesystem):
    test_file = isolated_filesystem / 'output.json'
    test_file.write_text(json.dumps({'status': 'ok'}))
"""

