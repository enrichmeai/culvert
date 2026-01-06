Feature: GDW Data Quality Validation
  As a Data Quality Steward
  I want to ensure that incoming data meets business quality rules
  So that downstream analytics are accurate

  @data_quality
  Scenario Outline: Validate record against business rules
    Given a record with <field> value "<value>"
    When I run the data quality validation
    Then the record should be marked as <status>
    And if invalid, the error message should contain "<error>"

    Examples:
      | field        | value       | status  | error                 |
      | loan_amount  | 5000        | valid   |                       |
      | loan_amount  | -100        | invalid | must be positive      |
      | loan_type    | MORTGAGE    | valid   |                       |
      | loan_type    | INVALID     | invalid | invalid loan type     |
      | ssn          | 123-45-6789 | valid   |                       |
      | ssn          | 000-00-0000 | invalid | cannot be all zeros   |
