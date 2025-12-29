import pytest
from gdw_data_core.core.validators import validate_ssn, validate_numeric_range, validate_date, validate_branch_code

def test_validate_ssn():
    # Valid SSN
    assert len(validate_ssn("123-45-6789")) == 0
    assert len(validate_ssn("123456789")) == 0
    
    # Invalid format
    errors = validate_ssn("123-45-678")
    assert len(errors) > 0
    assert "9 digits" in errors[0].message
    
    # All same digit
    errors = validate_ssn("111111111")
    assert len(errors) > 0
    
    # Invalid area
    errors = validate_ssn("666-45-6789")
    assert len(errors) > 0
    assert "area" in errors[0].message.lower()

def test_validate_numeric_range():
    # Valid
    val, errors = validate_numeric_range("age", "25", 18, 100)
    assert val == 25.0
    assert len(errors) == 0
    
    # Out of range
    val, errors = validate_numeric_range("age", "15", 18, 100)
    assert val is None
    assert len(errors) == 1
    
    # Non-numeric
    val, errors = validate_numeric_range("age", "abc", 18, 100)
    assert val is None
    assert len(errors) == 1

def test_validate_date():
    # Valid
    res, errors = validate_date("dob", "1990-01-01")
    assert res == "1990-01-01"
    assert len(errors) == 0
    
    # Invalid format
    res, errors = validate_date("dob", "01/01/1990")
    assert res is None
    assert len(errors) == 1
    
    # Future date
    from datetime import datetime, timedelta
    future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    res, errors = validate_date("dob", future_date)
    assert res is None
    assert len(errors) == 1

def test_validate_branch_code():
    # Valid
    assert len(validate_branch_code("NY1234")) == 0
    assert len(validate_branch_code("NY123456")) == 0
    
    # Invalid
    assert len(validate_branch_code("123456")) > 0
    assert len(validate_branch_code("N123")) > 0
