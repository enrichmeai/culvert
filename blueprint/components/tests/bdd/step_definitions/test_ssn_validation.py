import pytest
from gdw_data_core.testing.bdd import GDWScenarioTest
from gdw_data_core.testing.bdd.steps.common_steps import *

@GDWScenarioTest.run_scenario('../features/ssn_validation.feature', 'Validate SSN format')
def test_ssn_validation():
    pass
