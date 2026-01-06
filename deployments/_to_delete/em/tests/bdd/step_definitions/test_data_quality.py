from gcp_pipeline_tester import GDWScenarioTest


@GDWScenarioTest.run_scenario('../features/data_quality.feature', 'Validate record against business rules')
def test_data_quality():
    pass
