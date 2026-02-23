"""
Pipeline Builder Module

Test pipeline builder for testing.
"""

from typing import Optional, Callable
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline


class TestPipelineBuilder:
    """
    Fluent builder for test pipelines.

    Simplifies construction of test pipelines with common patterns.

    Example:
        >>> pipeline = (TestPipelineBuilder()
        ...     .with_input_data([1, 2, 3])
        ...     .add_transform(lambda x: x * 2)
        ...     .build())
    """

    def __init__(self):
        """Initialize test pipeline builder."""
        self.pipeline = TestPipeline()
        self.current_pcoll = None
        self.input_data = []
        self.transforms = []

    def with_input_data(self, data: list) -> 'TestPipelineBuilder':
        """
        Set input data for pipeline.

        Args:
            data: Input data elements

        Returns:
            TestPipelineBuilder for chaining
        """
        self.input_data = data
        return self

    def add_transform(self, transform_fn: Callable) -> 'TestPipelineBuilder':
        """
        Add a transformation function.

        Args:
            transform_fn: Function to apply to each element

        Returns:
            TestPipelineBuilder for chaining
        """
        self.transforms.append(('map', transform_fn))
        return self

    def add_filter(self, predicate_fn: Callable) -> 'TestPipelineBuilder':
        """
        Add a filter predicate.

        Args:
            predicate_fn: Function that returns True to keep element

        Returns:
            TestPipelineBuilder for chaining
        """
        self.transforms.append(('filter', predicate_fn))
        return self

    def build(self):
        """
        Build the test pipeline.

        Returns:
            Constructed PCollection
        """
        if not self.input_data:
            raise ValueError("Input data required")

        # Create initial PCollection
        pcoll = self.pipeline | 'CreateInput' >> beam.Create(self.input_data)

        # Apply transforms
        for i, (transform_type, fn) in enumerate(self.transforms):
            if transform_type == 'map':
                pcoll = pcoll | f'Transform{i}' >> beam.Map(fn)
            elif transform_type == 'filter':
                pcoll = pcoll | f'Filter{i}' >> beam.Filter(fn)

        return pcoll

    def run(self):
        """
        Run the pipeline.

        Returns:
            Pipeline result
        """
        pcoll = self.build()
        return self.pipeline.run()

