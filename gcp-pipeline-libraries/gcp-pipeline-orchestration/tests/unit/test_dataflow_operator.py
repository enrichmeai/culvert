import pytest
from unittest.mock import MagicMock, patch
import gcp_pipeline_orchestration.operators.dataflow as dataflow_mod
from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator, SourceType, ProcessingMode

class TestBaseDataflowOperator:
    def setup_method(self):
        # Ensure stubs are MagicMocks for the tests
        self.orig_python_op = dataflow_mod.DataflowCreatePythonJobOperator
        self.orig_flex_op = dataflow_mod.DataflowStartFlexTemplateOperator
        self.orig_classic_op = dataflow_mod.DataflowTemplatedJobStartOperator
        
        dataflow_mod.DataflowCreatePythonJobOperator = MagicMock()
        dataflow_mod.DataflowStartFlexTemplateOperator = MagicMock()
        dataflow_mod.DataflowTemplatedJobStartOperator = MagicMock()

    def teardown_method(self):
        dataflow_mod.DataflowCreatePythonJobOperator = self.orig_python_op
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
        mock_python_op = dataflow_mod.DataflowCreatePythonJobOperator
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
        # Check if parameters were passed as options
        options = kwargs['options']
        assert options['custom_flag'] == 'value'
        assert options['project'] == operator.project_id

    def test_execute_streaming_flex_template(self):
        mock_flex_op = dataflow_mod.DataflowStartFlexTemplateOperator
        operator = BaseDataflowOperator(
            task_id='test_task',
            pipeline_name='test-pipeline',
            source_type='pubsub',
            processing_mode='streaming',
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
            input_path='gs://in',
            output_table='p:d.t'
        )
        
        context = MagicMock()
        operator.execute(context)
        
        mock_classic_op.assert_called_once()
