import pytest
from unittest.mock import MagicMock, patch

# The template operators come from apache-airflow-providers-google; a Python job runs through
# apache-airflow-providers-apache-beam's operator. Without both, these tests skip (#88).
try:
    from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator  # noqa: F401
    from airflow.providers.apache.beam.operators.beam import BeamRunPythonPipelineOperator  # noqa: F401
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False

_SKIP_REASON = ("apache-airflow-providers-google and apache-airflow-providers-apache-beam "
                "are required for the Dataflow operators")

import data_pipeline_orchestration.operators.dataflow as dataflow_mod
from data_pipeline_orchestration.operators.dataflow import BaseDataflowOperator, SourceType, ProcessingMode

@pytest.mark.skipif(not AIRFLOW_AVAILABLE, reason=_SKIP_REASON)
class TestBaseDataflowOperator:
    def setup_method(self):
        # Ensure stubs are MagicMocks for the tests
        self.orig_python_op = dataflow_mod.BeamRunPythonPipelineOperator
        self.orig_flex_op = dataflow_mod.DataflowStartFlexTemplateOperator
        self.orig_classic_op = dataflow_mod.DataflowTemplatedJobStartOperator
        
        dataflow_mod.BeamRunPythonPipelineOperator = MagicMock()
        dataflow_mod.DataflowStartFlexTemplateOperator = MagicMock()
        dataflow_mod.DataflowTemplatedJobStartOperator = MagicMock()

    def teardown_method(self):
        dataflow_mod.BeamRunPythonPipelineOperator = self.orig_python_op
        dataflow_mod.DataflowStartFlexTemplateOperator = self.orig_flex_op
        dataflow_mod.DataflowTemplatedJobStartOperator = self.orig_classic_op

    def test_init(self):
        # Explicit test for initialization since it was failing
        operator = BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            source_type='gcs',
            processing_mode='batch'
        )
        assert operator.task_id == 'test_task'
        assert operator.pipeline_name == 'test-pipeline'

    def test_execute_python_job(self):
        mock_python_op = dataflow_mod.BeamRunPythonPipelineOperator
        operator = BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            use_template=False,
            job_code_path='gs://bucket/script.py',
            input_path='gs://in',
            output_table='p:d.t',
            additional_params={'custom_flag': 'value'}
        )
        
        context = MagicMock()
        operator.execute(context)
        
        mock_python_op.assert_called_once()
        args, kwargs = mock_python_op.call_args
        assert kwargs['py_file'] == 'gs://bucket/script.py'
        assert kwargs['runner'] == 'DataflowRunner'
        # Check if parameters were passed as options
        options = kwargs['pipeline_options']
        assert options['custom_flag'] == 'value'
        assert options['project'] == operator.project_id
        config = kwargs['dataflow_config']
        assert config.project_id == operator.project_id
        assert config.location == operator.region
        assert 'test-pipeline' in config.job_name

    def test_execute_streaming_flex_template(self):
        mock_flex_op = dataflow_mod.DataflowStartFlexTemplateOperator
        operator = BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            source_type='pubsub',
            processing_mode='streaming',
            template_type='flex',
            input_subscription='sub',
            output_table='p:d.t'
        )
        
        context = MagicMock()
        operator.execute(context)
        
        mock_flex_op.assert_called_once()
        args, kwargs = mock_flex_op.call_args
        assert kwargs['body']['launchParameter']['parameters']['processingMode'] == 'streaming'

    def test_execute_batch_classic_template(self):
        mock_classic_op = dataflow_mod.DataflowTemplatedJobStartOperator
        operator = BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            processing_mode='batch',
            template_type='classic',
            input_path='gs://in',
            output_table='p:d.t'
        )
        
        context = MagicMock()
        operator.execute(context)
        
        mock_classic_op.assert_called_once()

    def test_execute_batch_flex_template(self):
        """Test that batch mode with flex template uses FlexTemplateOperator."""
        mock_flex_op = dataflow_mod.DataflowStartFlexTemplateOperator
        operator = BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            processing_mode='batch',
            template_type='flex',  # Default is now flex
            input_path='gs://in',
            output_table='p:d.t'
        )
        
        context = MagicMock()
        operator.execute(context)
        
        mock_flex_op.assert_called_once()
        args, kwargs = mock_flex_op.call_args
        assert kwargs['body']['launchParameter']['parameters']['processingMode'] == 'batch'



@pytest.mark.skipif(not AIRFLOW_AVAILABLE, reason=_SKIP_REASON)
def test_the_template_operators_are_the_providers_own():
    # apache-airflow-providers-google 11.0.0 removed DataflowCreatePythonJobOperator. Imported in
    # one statement with it, the template operators, which still exist, became stubs too.
    from airflow.providers.google.cloud.operators import dataflow as provider

    assert dataflow_mod.DataflowTemplatedJobStartOperator is provider.DataflowTemplatedJobStartOperator
    assert dataflow_mod.DataflowStartFlexTemplateOperator is provider.DataflowStartFlexTemplateOperator
    assert dataflow_mod.DATAFLOW_OPERATORS_AVAILABLE


@pytest.mark.skipif(not AIRFLOW_AVAILABLE, reason=_SKIP_REASON)
def test_a_python_job_builds_the_real_beam_operator():
    # No mock of the operator class: the provider's own constructor checks the arguments.
    with patch.object(BeamRunPythonPipelineOperator, "execute", autospec=True, return_value="job-id") as run:
        operator = BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            use_template=False,
            job_code_path='gs://bucket/script.py',
            input_path='gs://in',
            output_table='p:d.t',
        )
        assert operator.execute(MagicMock()) == 'job-id'

    inner = run.call_args.args[0]
    assert isinstance(inner, BeamRunPythonPipelineOperator)
    assert inner.runner == 'DataflowRunner'
    assert inner.py_file == 'gs://bucket/script.py'
    assert inner.dataflow_config.project_id == operator.project_id
    assert inner.dataflow_config.location == operator.region
    assert inner.dataflow_config.cancel_timeout == 10 * 60


@pytest.mark.skipif(not AIRFLOW_AVAILABLE, reason=_SKIP_REASON)
@pytest.mark.parametrize("mode, streaming", [("batch", False), ("streaming", True)])
def test_a_python_jobs_options_parse_in_beam(mode, streaming):
    # The provider turns pipeline_options into the command line the job's script gets, and the
    # script parses it with Beam's PipelineOptions. Beam's --streaming is a flag: given a value
    # ("--streaming=false") its parser exits with status 2, and the job fails at start-up.
    pytest.importorskip("apache_beam")
    from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, WorkerOptions
    from airflow.providers.apache.beam.hooks.beam import beam_options_to_args

    with patch.object(BeamRunPythonPipelineOperator, "execute", autospec=True) as run:
        BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            processing_mode=mode,
            use_template=False,
            job_code_path='gs://bucket/script.py',
            input_path='gs://in',
            output_table='p:d.t',
            max_workers=7,
        ).execute(MagicMock())

    args = beam_options_to_args(run.call_args.args[0].pipeline_options)
    options = PipelineOptions(args)
    assert options.view_as(StandardOptions).streaming is streaming
    assert options.view_as(WorkerOptions).max_num_workers == 7
