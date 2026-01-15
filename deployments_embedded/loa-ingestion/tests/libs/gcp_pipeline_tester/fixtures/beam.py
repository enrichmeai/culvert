"""
Beam Fixtures Module

Test fixtures for Apache Beam pipeline testing.
"""

import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.options.pipeline_options import PipelineOptions


@pytest.fixture
def test_pipeline() -> TestPipeline:
    """
    Fixture providing a TestPipeline instance.

    Returns a fresh TestPipeline for each test, suitable for
    testing Beam transforms in isolation.

    Returns:
        TestPipeline instance

    Example:
        >>> def test_transform(test_pipeline):
        ...     result = test_pipeline | beam.Create([1, 2, 3])
        ...     test_pipeline.run()
    """
    return TestPipeline()


@pytest.fixture
def beam_options() -> PipelineOptions:
    """
    Fixture providing test PipelineOptions.

    Returns:
        PipelineOptions configured for testing

    Example:
        >>> def test_with_options(beam_options):
        ...     pipeline = beam.Pipeline(options=beam_options)
    """
    return PipelineOptions()


@pytest.fixture
def sample_beam_record() -> dict:
    """
    Fixture providing a sample record for Beam processing.

    Returns:
        Dictionary representing a typical data record

    Example:
        >>> def test_process_record(sample_beam_record):
        ...     assert 'id' in sample_beam_record
    """
    return {
        'id': '1',
        'name': 'Test Record',
        'value': 100,
        'status': 'active'
    }

