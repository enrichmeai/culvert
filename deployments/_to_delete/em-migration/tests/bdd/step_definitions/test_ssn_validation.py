from gcp_pipeline_tester import GDWScenarioTest


@GDWScenarioTest.run_scenario('../features/ssn_validation.feature', 'Validate SSN format')
def test_ssn_validation():
    pass
