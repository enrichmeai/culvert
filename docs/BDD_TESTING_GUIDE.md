# BDD Testing Guide - The Right Way

This guide explains how to implement Behavior-Driven Development (BDD) tests in the Generic Blueprint using the standardized `gcp_pipeline_core.testing.bdd` library.

## 🎯 Architecture

We follow a tiered approach to BDD to maximize reusability:

1.  **Core Library (`gcp_pipeline_core`)**: Contains reusable step definitions and base test classes.
2.  **Blueprint Features**: Human-readable `.feature` files defining business requirements.
3.  **Blueprint Step Definitions**: Thin mapping files that link features to library steps.

## 🚀 How to Implement a New BDD Test

### 1. Create a Feature File
Create a `.feature` file in `deployments/src/tests/bdd/features/`.

Example `my_feature.feature`:
```gherkin
Feature: My New Feature
  Scenario: Do something important
    Given a certain condition
    When I perform an action
    Then I expect a result
```

### 2. Check for Reusable Steps
Before writing new Python code, check if the steps are already available in `gcp_pipeline_core.testing.bdd.steps`:
- `common_steps`: Basic validations (SSN, etc.)
- `pipeline_steps`: End-to-end pipeline flow (GCS -> Dataflow -> BQ)
- `dq_steps`: Data quality business rules

### 3. Create the Step Definition File
Create a `.py` file in `deployments/src/tests/bdd/step_definitions/`. Use the `GDWScenarioTest` helper.

Example `test_my_feature.py`:

```python
from gcp_pipeline_core.testing import GDWScenarioTest
from gcp_pipeline_core.testing import *


# Import other step modules as needed

@GDWScenarioTest.run_scenario('../features/my_feature.feature', 'Do something important')
def test_my_feature():
    pass
```

## 🛠️ Reusable Library Components

### GDWScenarioTest
The base class for BDD tests. It provides:
- `run_scenario(feature_path, scenario_name)`: A static method that handles relative path resolution for feature files.

### Common Steps
Importing `common_steps` gives you:
- `Given an SSN "<ssn>"`
- `When I validate the SSN`
- `Then the validation should return <n> errors`

### Pipeline Steps
Importing `pipeline_steps` gives you:
- `Given a valid application file "<file>" in the GCS landing zone`
- `When the Generic migration pipeline is triggered for "<job>"`
- `Then the input file should be validated successfully`
- `And the Dataflow job should complete successfully`
- ...and more.

## 📊 Running Tests

```bash
# Run all BDD tests
pytest deployments/src/tests/bdd/step_definitions/

# Run a specific test
pytest deployments/src/tests/bdd/step_definitions/test_data_quality.py
```
