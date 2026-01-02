import pytest
from gdw_data_core.testing.bdd import GDWScenarioTest
from gdw_data_core.testing.bdd.steps.pipeline_steps import *

@GDWScenarioTest.run_scenario('../features/pipeline_e2e.feature', 'Process a valid application file through the pipeline')
def test_pipeline_e2e():
    pass
