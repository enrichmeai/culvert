import pytest
from datetime import datetime
from gcp_pipeline_orchestration import DAGFactory, ValidationError

class TestDAGFactory:
    def setup_method(self):
        """Reset DAG IDs before each test."""
        factory = DAGFactory()
        factory.reset_created_dag_ids()

    def test_create_dag_basic(self):
        """Test creating a basic DAG."""
        factory = DAGFactory()
        dag = factory.create_dag(
            dag_id='test_dag_001',
            schedule_interval='@daily'
        )

        assert dag.dag_id == 'test_dag_001'
        assert dag.schedule == '@daily'
        assert 'gdw' in dag.tags

    def test_create_dag_with_custom_args(self):
        """Test creating DAG with custom default_args."""
        default_args = {
            'owner': 'test_team',
            'retries': 5,
            'email': 'test@example.com'
        }

        factory = DAGFactory()
        dag = factory.create_dag(
            dag_id='test_dag_002',
            default_args=default_args
        )

        assert dag.default_args['owner'] == 'test_team'
        assert dag.default_args['retries'] == 5
        assert dag.default_args['email'] == 'test@example.com'

    def test_validate_dag_config_valid(self):
        """Test valid DAG configuration validation."""
        config = {
            'dag_id': 'valid_dag',
            'schedule_interval': '@daily',
            'start_date': '2023-01-01'
        }

        # Should not raise
        factory = DAGFactory()
        factory.create_dag_from_dict(config)

    def test_validate_dag_config_missing_dag_id(self):
        """Test validation fails without dag_id."""
        config = {
            'schedule_interval': '@daily'
        }

        factory = DAGFactory()
        with pytest.raises(Exception):
            factory.create_dag_from_dict(config)

    def test_validate_dag_config_duplicate_dag_id(self):
        """Test validation fails with duplicate dag_id."""
        factory = DAGFactory()
        factory.create_dag(dag_id='test_dag')

        config = {'dag_id': 'test_dag'}

        with pytest.raises(Exception):
            factory.create_dag_from_dict(config)

    def test_create_dag_from_config(self):
        """Test creating DAG from configuration dict."""
        config = {
            'dag_id': 'loa_daily_job',
            'schedule_interval': '@daily',
            'start_date': '2023-01-01',
            'catchup': False,
            'default_args': {
                'owner': 'loa_team',
                'retries': 3,
                'retry_delay_minutes': 5
            },
            'tags': ['loa', 'migration']
        }

        factory = DAGFactory()
        dag = factory.create_dag_from_dict(config)

        assert dag.dag_id == 'loa_daily_job'
        assert dag.default_args['owner'] == 'loa_team'
        assert dag.default_args['retries'] == 3
        assert 'loa' in dag.tags

    def test_create_dag_from_config_with_invalid_start_date(self):
        """Test DAG creation handles invalid start date gracefully."""
        config = {
            'dag_id': 'test_dag_bad_date',
            'start_date': 'invalid-date'
        }

        # Should not raise, uses default
        factory = DAGFactory()
        dag = factory.create_dag_from_dict(config)
        assert dag.dag_id == 'test_dag_bad_date'

