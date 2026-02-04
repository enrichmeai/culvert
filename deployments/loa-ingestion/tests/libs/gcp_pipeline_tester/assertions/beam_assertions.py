"""
Beam Assertions Module

Custom assertions for Beam pipeline testing.
"""

from typing import Any, Iterable, Callable


def assert_pcollection_equal(pcoll: Any, expected: Iterable[Any], msg: str = "") -> None:
    """
    Assert that a PCollection contains exactly the expected elements.

    Args:
        pcoll: PCollection to check
        expected: Expected elements
        msg: Optional failure message

    Raises:
        AssertionError: If PCollection doesn't match expected

    Example:
        >>> from apache_beam.testing.util import assert_that, equal_to
        >>> pipeline = TestPipeline()
        >>> result = pipeline | beam.Create([1, 2, 3])
        >>> assert_that(result, equal_to([1, 2, 3]))
    """
    from apache_beam.testing.util import assert_that, equal_to
    assert_that(pcoll, equal_to(list(expected)))


def assert_record_structure(record: dict, required_fields: list, msg: str = "") -> None:
    """
    Assert that a record has all required fields.

    Args:
        record: Dictionary to check
        required_fields: List of required field names
        msg: Optional failure message

    Raises:
        AssertionError: If required fields are missing

    Example:
        >>> assert_record_structure(record, ['id', 'name', 'email'])
    """
    missing = [f for f in required_fields if f not in record]
    assert not missing, f"Missing fields: {missing}. {msg}"


def assert_beam_transform_output(
    input_data: Iterable[Any],
    transform_fn: Callable,
    expected_output: Iterable[Any],
    msg: str = ""
) -> None:
    """
    Assert that a Beam transform produces expected output.

    Args:
        input_data: Input data for transform
        transform_fn: Transform function to test
        expected_output: Expected output
        msg: Optional failure message

    Example:
        >>> def double(x):
        ...     return x * 2
        >>>
        >>> assert_beam_transform_output(
        ...     [1, 2, 3],
        ...     double,
        ...     [2, 4, 6]
        ... )
    """
    from apache_beam.testing.test_pipeline import TestPipeline
    import apache_beam as beam
    from apache_beam.testing.util import assert_that, equal_to

    pipeline = TestPipeline()
    result = (
        pipeline
        | 'CreateInput' >> beam.Create(input_data)
        | 'Transform' >> beam.Map(transform_fn)
    )
    assert_that(result, equal_to(list(expected_output)))
    pipeline.run()

