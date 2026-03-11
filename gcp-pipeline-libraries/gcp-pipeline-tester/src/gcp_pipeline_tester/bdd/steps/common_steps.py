"""
Common BDD steps for GCP pipelines.
"""

from pytest_bdd import given, when, then, parsers
from gcp_pipeline_tester.validators import validate_ssn

@given(parsers.re(r'an SSN "(?P<ssn>.*)"'), target_fixture="ssn_context")
def step_given_ssn(ssn):
    return {"ssn": ssn}

@when('I validate the SSN', target_fixture="validation_results")
def step_when_validate_ssn(ssn_context):
    return validate_ssn(ssn_context["ssn"])

@then(parsers.parse('the validation should return {expected_error_count:d} errors'))
def step_then_check_errors(validation_results, expected_error_count):
    assert len(validation_results) == expected_error_count
