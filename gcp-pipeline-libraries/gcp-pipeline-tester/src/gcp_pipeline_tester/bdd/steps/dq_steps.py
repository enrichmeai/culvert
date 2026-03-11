"""
Data quality BDD steps for GCP pipelines.
"""

from pytest_bdd import given, when, then, parsers
from gcp_pipeline_tester.validators import validate_ssn

def mock_validate_loan_amount(value):
    try:
        amount = float(value)
        if amount <= 0:
            return [{"field": "loan_amount", "message": "must be positive"}]
        return []
    except ValueError:
        return [{"field": "loan_amount", "message": "must be numeric"}]

def mock_validate_loan_type(value):
    valid_types = ['MORTGAGE', 'PERSONAL', 'AUTO', 'HOME_EQUITY']
    if value not in valid_types:
        return [{"field": "loan_type", "message": "invalid loan type"}]
    return []

@given(parsers.parse('a record with {field} value "{value}"'), target_fixture="dq_context")
def step_given_dq_record(field, value):
    return {"field": field, "value": value}

@when('I run the data quality validation', target_fixture="dq_results")
def step_when_run_dq(dq_context):
    field = dq_context["field"]
    value = dq_context["value"]

    if field == "ssn":
        errors = validate_ssn(value)
        return [{"field": e.field, "message": e.message} for e in errors]
    elif field == "loan_amount":
        return mock_validate_loan_amount(value)
    elif field == "loan_type":
        return mock_validate_loan_type(value)
    return []

@then(parsers.parse('the record should be marked as {status}'))
def step_then_check_dq_status(dq_results, status):
    is_valid = len(dq_results) == 0
    expected_valid = (status == "valid")
    assert is_valid == expected_valid, f"Expected {status}, but got {'valid' if is_valid else 'invalid'}"

@then(parsers.re(r'if invalid, the error message should contain "(?P<error>.*)"'))
def step_then_check_dq_error(dq_results, error):
    if error:
        messages = [e["message"].lower() for e in dq_results]
        assert any(error.lower() in m for m in messages), f"Error '{error}' not found in {messages}"
