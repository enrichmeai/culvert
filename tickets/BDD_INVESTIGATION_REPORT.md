### BDD Testing Framework Investigation Report

#### Executive Summary
This report evaluates Behavior-Driven Development (BDD) frameworks for the LOA Blueprint. Based on the existing technical stack (Python, Pytest, GCP, dbt), `pytest-bdd` is recommended as the primary BDD framework. A successful Proof of Concept (PoC) was implemented for data validation logic.

#### Evaluated Frameworks

| Framework | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- |
| **pytest-bdd** | Native integration with `pytest`, leverages existing fixtures, unified reporting. | Slightly different decorators than standard Cucumber. | **Primary Choice** |
| **Behave** | Most popular Python BDD framework, strictly follows Gherkin. | Requires separate runner from `pytest`, harder to share fixtures. | Alternative for standalone QA teams. |
| **Robot Framework** | Keyword-driven, excellent for acceptance testing and RPA. | Steeper learning curve for developers, less "pythonic" for unit tests. | Not recommended for core logic. |

#### Proof of Concept (PoC) Results
A PoC was implemented for the `validate_ssn` logic in the `gdw_data_core` module.

- **Feature File**: `blueprint/components/tests/bdd/features/ssn_validation.feature`
- **Step Definitions**: `blueprint/components/tests/bdd/step_definitions/test_ssn_validation.py`
- **Execution**: `pytest blueprint/components/tests/bdd/step_definitions/test_ssn_validation.py`
- **Result**: 7/7 scenarios passed (including edge cases like invalid area codes and empty strings).

#### BDD for dbt (Data Transformation)
For `dbt` transformations, BDD can be achieved through:
1. **dbt Unit Tests**: (Native in dbt 1.8+) Define test cases in YAML.
2. **pytest-bdd with BigQuery**: Integration tests that load mock data into BigQuery, run `dbt`, and verify results using BDD steps.

#### BDD Library Implementation
The BDD framework has been extracted to the `gdw_data_core.testing.bdd` package to ensure reusability across platforms.

- **Base Class**: `gdw_data_core.testing.bdd.base.GDWScenarioTest` provides a `run_scenario` helper that manages relative paths for feature files.
- **Reusable Steps**:
    - `gdw_data_core.testing.bdd.steps.common_steps`: Generic validation steps (e.g., SSN).
    - `gdw_data_core.testing.bdd.steps.pipeline_steps`: Pipeline lifecycle steps (GCS to BigQuery).
    - `gdw_data_core.testing.bdd.steps.dq_steps`: Data quality business rule validation.

#### Blueprint Demonstration
The LOA Blueprint demonstrates the "Right Way" to implement BDD by:
1.  **Defining Features**: Human-readable Gherkin files in `blueprint/components/tests/bdd/features/`.
2.  **Mapping to Library Steps**: Test files in `blueprint/components/tests/bdd/step_definitions/` that import reusable steps from the library.
3.  **Minimal Boilerplate**: Blueprint test files only need to link the feature file to the scenario using `GDWScenarioTest.run_scenario`.

#### Recommendations
1. **Adopt `pytest-bdd`**: Standardize on `pytest-bdd` for all BDD-style testing in the LOA Blueprint.
2. **Library First**: Always look to implement generic steps in `gdw_data_core` library first before creating project-specific steps.
3. **Directory Structure**: Organize BDD tests under `components/tests/bdd/` with `features/` and `step_definitions/` subdirectories.
4. **CI/CD Integration**: Add `pytest-bdd` to `requirements-test.txt` and ensure BDD tests are part of the CI pipeline.

#### Next Steps
- Create implementation tickets for high-priority pipeline components.
- Standardize BDD reporting (e.g., using `pytest-html` or `allure-pytest`).

#### End-to-End Pipeline BDD Strategy
To ensure reliability in lower environments, we have extended BDD to cover the full end-to-end pipeline.

- **Feature**: `blueprint/components/tests/bdd/features/pipeline_e2e.feature`
- **Step Definitions**: `blueprint/components/tests/bdd/step_definitions/test_pipeline_e2e.py`
- **Integration**:
    - Added `pytest-bdd` to `requirements-test.txt`.
    - Integrated into `validate_deployment.sh` for pre-deployment checks.
    - Added to GitHub Actions (`gcp-deployment-tests.yml`) for automated validation in the Staging environment.
- **Key Scenarios**:
    - Happy path: Valid file arrival → Validation → Dataflow → BigQuery → Archival → Notification.
    - Error handling: Invalid file arrival → Error detection → Error table insertion → Alerting.
