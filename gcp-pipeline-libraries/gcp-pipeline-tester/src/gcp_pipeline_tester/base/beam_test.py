"""
Beam Test Module

Base test class for Apache Beam pipeline tests.
"""

from typing import List, Any, Iterable

import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

from .pipeline_test import BasePipelineTest


class BaseBeamTest(BasePipelineTest):
    """
    Base class for Apache Beam pipeline tests.

    Provides utilities and assertion methods for testing Beam transforms
    and pipelines. Simplifies testing of DoFn classes and complex transforms.

    Example:
        >>> class TestTransforms(BaseBeamTest):
        ...     def test_parse_csv(self):
        ...         pipeline = self.create_test_pipeline()
        ...         input_data = ['1,John', '2,Jane']
        ...         expected = [{'id': '1', 'name': 'John'}, ...]
        ...
        ...         result = (
        ...             pipeline
        ...             | beam.Create(input_data)
        ...             | beam.ParDo(ParseCsvLine(['id', 'name']))
        ...         )
        ...         self.assert_pcollection_equal(result, expected)
        ...         pipeline.run()
    """

    def create_test_pipeline(self) -> TestPipeline:
        """
        Create a Beam test pipeline.

        Returns a TestPipeline instance suitable for testing transforms
        and complete pipelines. Test pipelines execute synchronously
        and allow easy assertion of results.

        Returns:
            TestPipeline: Apache Beam test pipeline instance

        Example:
            >>> pipeline = self.create_test_pipeline()
            >>> result = pipeline | beam.Create([1, 2, 3]) | beam.Map(lambda x: x * 2)
            >>> pipeline.run()
        """
        return TestPipeline()

    def assert_pcollection_equal(self, pcoll: Any, expected_data: Iterable[Any]) -> None:
        """
        Assert that a PCollection contains the expected data.

        Adds a matcher assertion to the pipeline that verifies the PCollection
        contains exactly the expected elements (in any order).

        Args:
            pcoll: PCollection to verify
            expected_data: Expected elements

        Example:
            >>> pipeline = self.create_test_pipeline()
            >>> result = pipeline | beam.Create([1, 2, 3])
            >>> self.assert_pcollection_equal(result, [1, 2, 3])
            >>> pipeline.run()
        """
        assert_that(pcoll, equal_to(list(expected_data)))

    def assert_pcollection_not_empty(self, pcoll: Any) -> None:
        """
        Assert that a PCollection is not empty.

        Args:
            pcoll: PCollection to check

        Example:
            >>> pipeline = self.create_test_pipeline()
            >>> result = pipeline | beam.Create([1, 2, 3])
            >>> self.assert_pcollection_not_empty(result)
            >>> pipeline.run()
        """
        def check_not_empty(items):
            assert len(items) > 0, "PCollection is empty"

        assert_that(pcoll, check_not_empty)

    def assert_pcollection_empty(self, pcoll: Any) -> None:
        """
        Assert that a PCollection is empty.

        Args:
            pcoll: PCollection to check

        Example:
            >>> pipeline = self.create_test_pipeline()
            >>> result = (
            ...     pipeline
            ...     | beam.Create([1, 2, 3])
            ...     | beam.Filter(lambda x: x > 100)
            ... )
            >>> self.assert_pcollection_empty(result)
            >>> pipeline.run()
        """
        assert_that(pcoll, equal_to([]))

    def assert_pcollection_contains(self, pcoll: Any, expected_element: Any) -> None:
        """
        Assert that a PCollection contains a specific element.

        Args:
            pcoll: PCollection to check
            expected_element: Element that should be in PCollection

        Example:
            >>> pipeline = self.create_test_pipeline()
            >>> result = pipeline | beam.Create([1, 2, 3])
            >>> self.assert_pcollection_contains(result, 2)
            >>> pipeline.run()
        """
        def check_contains(items):
            assert expected_element in items, \
                f"Element {expected_element} not found in PCollection"

        assert_that(pcoll, check_contains)

    def assert_pcollection_count(self, pcoll: Any, expected_count: int) -> None:
        """
        Assert that a PCollection has the expected number of elements.

        Args:
            pcoll: PCollection to check
            expected_count: Expected number of elements

        Example:
            >>> pipeline = self.create_test_pipeline()
            >>> result = pipeline | beam.Create([1, 2, 3])
            >>> self.assert_pcollection_count(result, 3)
            >>> pipeline.run()
        """
        def check_count(items):
            assert len(items) == expected_count, \
                f"Expected {expected_count} elements, got {len(items)}"

        assert_that(pcoll, check_count)

