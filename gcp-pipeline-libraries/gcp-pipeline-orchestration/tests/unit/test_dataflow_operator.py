import pytest
from unittest.mock import MagicMock, patch
from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator, SourceType, ProcessingMode

class TestBaseDataflowOperator:
    @patch('gcp_pipeline_orchestration.operators.dataflow.DataflowCreatePythonJobOperator')
    def test_execute_python_job(self, mock_python_op):
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

    @patch('gcp_pipeline_orchestration.operators.dataflow.DataflowStartFlexTemplateOperator')
    def test_execute_streaming_flex_template(self, mock_flex_op):
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

    @patch('gcp_pipeline_orchestration.operators.dataflow.DataflowTemplatedJobStartOperator')
    def test_execute_batch_classic_template(self, mock_classic_op):
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
