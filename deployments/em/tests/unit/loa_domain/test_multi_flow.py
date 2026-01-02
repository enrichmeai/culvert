import unittest
from blueprint.em.components.loa_domain.validation import (
    validate_customer_record,
    validate_branch_record,
    validate_collateral_record
)
from gdw_data_core.testing import BaseValidationTest

class TestMultiFlowValidation(BaseValidationTest):
    def test_customer_validation(self):
        record = {
            "customer_id": "CUST001",
            "ssn": "123-45-6789",
            "credit_score": "750",
            "branch_code": "NY1234"
        }
        validated, errors = validate_customer_record(record)
        self.assertValidationPassed(errors)
        self.assertEqual(validated["credit_score"], 750)

    def test_branch_validation(self):
        record = {
            "branch_code": "NY1234",
            "employee_count": "45"
        }
        validated, errors = validate_branch_record(record)
        self.assertValidationPassed(errors)
        self.assertEqual(validated["employee_count"], 45)

    def test_collateral_validation(self):
        record = {
            "collateral_id": "COL001",
            "collateral_type": "PROPERTY",
            "collateral_value": "350000"
        }
        validated, errors = validate_collateral_record(record)
        self.assertValidationPassed(errors)
        self.assertEqual(validated["collateral_value"], 350000)

if __name__ == "__main__":
    unittest.main()
