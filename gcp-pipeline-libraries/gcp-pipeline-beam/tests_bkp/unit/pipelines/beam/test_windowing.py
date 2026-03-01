import pytest
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to
from gcp_pipeline_beam.pipelines.beam.transforms.windowing import ApplyWindowing

from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions

def test_apply_windowing_fixed():
    # Set streaming=True to trigger some internal Beam logic if needed
    options = PipelineOptions()
    options.view_as(StandardOptions).streaming = True
    # Disable type checking as it fails in some environments with isinstance error
    options.view_as(beam.options.pipeline_options.TypeOptions).pipeline_type_check = False
    
    with TestPipeline(options=options) as p:
        elements = [
            (1, 'a'), # 1s
            (2, 'b'), # 2s
            (61, 'c'), # 61s
        ]
        
        pcoll = (
            p 
            | beam.Create(elements)
            | beam.Map(lambda x: beam.window.TimestampedValue(x[1], x[0]))
            | ApplyWindowing(window_type='fixed', size=60)
            | beam.CombineGlobally(beam.combiners.CountCombineFn()).without_defaults()
        )
        
        assert_that(pcoll, equal_to([2, 1]))

def test_apply_windowing_sliding():
    # Set streaming=True to trigger some internal Beam logic if needed
    options = PipelineOptions()
    options.view_as(StandardOptions).streaming = True
    # Disable type checking as it fails in some environments with isinstance error
    options.view_as(beam.options.pipeline_options.TypeOptions).pipeline_type_check = False

    with TestPipeline(options=options) as p:
        elements = [
            (1, 'a'),
            (31, 'b'),
        ]
        # Sliding window 60s, period 30s
        # Window 1: [-30, 30) -> has 'a'
        # Window 2: [0, 60) -> has 'a' and 'b'
        # Window 3: [30, 90) -> has 'b'
        
        pcoll = (
            p
            | beam.Create(elements)
            | beam.Map(lambda x: beam.window.TimestampedValue(x[1], x[0]))
            | ApplyWindowing(window_type='sliding', size=60, period=30)
            | beam.CombineGlobally(beam.combiners.CountCombineFn()).without_defaults()
        )
        
        # Expecting counts from 3 windows: 1 ('a'), 2 ('a','b'), 1 ('b')
        assert_that(pcoll, equal_to([1, 2, 1]))
