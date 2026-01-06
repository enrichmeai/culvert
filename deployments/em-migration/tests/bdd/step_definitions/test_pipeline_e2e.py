from gcp_pipeline_tester import GDWScenarioTest


@GDWScenarioTest.run_scenario('../features/pipeline_e2e.feature', 'Process a valid application file through the pipeline')
def test_pipeline_e2e():
    pass
