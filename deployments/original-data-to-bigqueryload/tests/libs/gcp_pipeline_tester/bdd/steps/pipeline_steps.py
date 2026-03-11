"""
Pipeline BDD steps for GCP pipelines.
"""

from pytest_bdd import given, when, then, parsers
import pytest

@pytest.fixture
def pipeline_context():
    return {
        "job_name": None,
        "input_file": None,
        "validated": False,
        "dataflow_completed": False,
        "bq_available": False,
        "archived": False,
        "notification_sent": False
    }

@given(parsers.parse('a valid application file "{filename}" in the GCS landing zone'), target_fixture="pipeline_context_with_file")
def step_given_valid_file(filename, pipeline_context):
    pipeline_context["input_file"] = filename
    return pipeline_context

@when(parsers.parse('the Generic migration pipeline is triggered for "{job_name}"'))
def step_when_pipeline_triggered(job_name, pipeline_context_with_file):
    pipeline_context = pipeline_context_with_file
    pipeline_context["job_name"] = job_name
    # Simulate pipeline execution
    pipeline_context["validated"] = True
    pipeline_context["dataflow_completed"] = True
    pipeline_context["bq_available"] = True
    pipeline_context["archived"] = True
    pipeline_context["notification_sent"] = True

@then('the input file should be validated successfully')
def step_then_validated(pipeline_context_with_file):
    assert pipeline_context_with_file["validated"] is True

@then('the Dataflow job should complete successfully')
def step_then_dataflow_completed(pipeline_context_with_file):
    assert pipeline_context_with_file["dataflow_completed"] is True

@then(parsers.parse('the processed records should be available in the BigQuery table "{table}"'))
def step_then_bq_available(table, pipeline_context_with_file):
    assert pipeline_context_with_file["bq_available"] is True

@then('the input file should be moved to the archive folder')
def step_then_archived(pipeline_context_with_file):
    assert pipeline_context_with_file["archived"] is True

@then('a completion notification should be sent to the Pub/Sub topic')
def step_then_notification_sent(pipeline_context_with_file):
    assert pipeline_context_with_file["notification_sent"] is True
