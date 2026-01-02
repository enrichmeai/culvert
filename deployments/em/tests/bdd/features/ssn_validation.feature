Feature: SSN Validation
  As a QA Engineer
  I want to validate SSN format and rules
  So that I can ensure data quality in the LOA Blueprint

  Scenario Outline: Validate SSN format
    Given an SSN "<ssn>"
    When I validate the SSN
    Then the validation should return <expected_error_count> errors

    Examples:
      | ssn           | expected_error_count |
      | 123-45-6789   | 0                    |
      | 123456789     | 0                    |
      | 123-45-678    | 1                    |
      | 111111111     | 1                    |
      | 666-45-6789   | 1                    |
      | 900-45-6789   | 1                    |
      |               | 1                    |
