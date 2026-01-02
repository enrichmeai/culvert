import pytest
from gdw_data_core.testing.bdd import GDWScenarioTest
from gdw_data_core.testing.bdd.steps.dq_steps import *

@GDWScenarioTest.run_scenario('../features/data_quality.feature', 'Validate record against business rules')
def test_data_quality():
    pass
