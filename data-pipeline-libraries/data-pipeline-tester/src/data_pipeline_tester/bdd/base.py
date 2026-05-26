"""
Base BDD classes for GCP pipelines.
"""

import pytest
from pytest_bdd import scenario, given, when, then, parsers

class PipelineScenarioTest:
    """
    Base class for pipeline BDD scenarios.
    Provides common fixtures and utility methods.
    """

    @pytest.fixture
    def scenario_context(self):
        """
        Shared context for BDD steps.
        """
        return {}

    @staticmethod
    def run_scenario(feature_file, scenario_name):
        """
        Decorator to link a test function to a scenario.
        Handles relative paths from the caller's file.
        """
        import inspect
        import os

        # Get the caller's file path
        caller_frame = inspect.stack()[1]
        caller_filename = caller_frame.filename
        caller_dir = os.path.dirname(os.path.abspath(caller_filename))

        # Resolve the feature file path relative to the caller
        abs_feature_path = os.path.normpath(os.path.join(caller_dir, feature_file))

        return scenario(abs_feature_path, scenario_name)
