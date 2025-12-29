"""
Tests for Pipeline Router Module

Tests the router for dynamic file type detection and pipeline configuration.
Located in: unit/orchestration/test_router.py
"""

import pytest
from gdw_data_core.orchestration.routing import (
    DAGRouter,
    PipelineConfig,
    FileType,
    ProcessingMode,
)


class TestDAGRouter:
    """Test suite for DAGRouter class."""

    def setup_method(self):
        """Create fresh router for each test."""
        self.router = DAGRouter()

    def test_router_initialization(self):
        """Test router initializes with empty pipelines."""
        assert len(self.router.pipelines) == 0
        assert len(self.router.get_registered_file_types()) == 0

    def test_register_pipeline(self):
        """Test registering a pipeline configuration."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='test_pipeline',
            entity_name='test_entity',
            table_name='stg_test_entity',
            required_columns=['id', 'name'],
        )

        self.router.register_pipeline(config)

        assert FileType.DATA in self.router.pipelines
        assert self.router.get_pipeline_config(FileType.DATA) == config

    def test_get_pipeline_config_exists(self):
        """Test getting registered pipeline configuration."""
        config = PipelineConfig(
            file_type=FileType.METADATA,
            dag_id='metadata_pipeline',
            entity_name='metadata_entity',
            table_name='stg_metadata',
            required_columns=['key', 'value'],
        )

        self.router.register_pipeline(config)
        retrieved = self.router.get_pipeline_config(FileType.METADATA)

        assert retrieved == config

    def test_get_pipeline_config_not_exists(self):
        """Test getting non-existent pipeline configuration returns None."""
        result = self.router.get_pipeline_config(FileType.LOGS)

        assert result is None

    def test_validate_file_structure_valid(self):
        """Test validating file structure with all required columns."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='validate_test',
            entity_name='test',
            table_name='stg_test',
            required_columns=['col1', 'col2', 'col3'],
        )

        self.router.register_pipeline(config)

        # File has all required columns plus extra
        csv_columns = ['col1', 'col2', 'col3', 'col4', 'col5']
        is_valid, missing = self.router.validate_file_structure(FileType.DATA, csv_columns)

        assert is_valid is True
        assert missing == []

    def test_validate_file_structure_missing_columns(self):
        """Test validating file structure with missing required columns."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='validate_test_2',
            entity_name='test',
            table_name='stg_test',
            required_columns=['col1', 'col2', 'col3'],
        )

        self.router.register_pipeline(config)

        # File is missing col2 and col3
        csv_columns = ['col1', 'col4', 'col5']
        is_valid, missing = self.router.validate_file_structure(FileType.DATA, csv_columns)

        assert is_valid is False
        assert 'col2' in missing
        assert 'col3' in missing

    def test_validate_file_structure_no_pipeline(self):
        """Test validating file structure when no pipeline is registered."""
        csv_columns = ['col1', 'col2']
        is_valid, missing = self.router.validate_file_structure(FileType.LOGS, csv_columns)

        assert is_valid is False
        assert len(missing) > 0

    def test_detect_file_type_by_extension(self):
        """Test detecting file type by file extension."""
        assert self.router.detect_file_type('data.csv') == FileType.DATA
        assert self.router.detect_file_type('data.txt') == FileType.DATA
        assert self.router.detect_file_type('metadata.json') == FileType.METADATA
        assert self.router.detect_file_type('metadata.xml') == FileType.METADATA
        assert self.router.detect_file_type('app.log') == FileType.LOGS

    def test_detect_file_type_unknown(self):
        """Test detecting unknown file type."""
        assert self.router.detect_file_type('unknown.xyz') == FileType.UNKNOWN
        assert self.router.detect_file_type('') == FileType.UNKNOWN

    def test_register_file_type_pattern(self):
        """Test registering custom file type pattern."""
        self.router.register_file_type_pattern(r'.*_data\..*', FileType.DATA)

        detected = self.router.detect_file_type('customer_data.csv')
        assert detected == FileType.DATA

    def test_get_registered_file_types(self):
        """Test getting list of registered file types."""
        config1 = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='data_pipeline',
            entity_name='data',
            table_name='stg_data',
            required_columns=['id'],
        )

        config2 = PipelineConfig(
            file_type=FileType.METADATA,
            dag_id='meta_pipeline',
            entity_name='meta',
            table_name='stg_meta',
            required_columns=['key'],
        )

        self.router.register_pipeline(config1)
        self.router.register_pipeline(config2)

        file_types = self.router.get_registered_file_types()
        assert FileType.DATA in file_types
        assert FileType.METADATA in file_types

    def test_unregister_pipeline(self):
        """Test unregistering a pipeline configuration."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='unreg_test',
            entity_name='unreg',
            table_name='stg_unreg',
            required_columns=['id'],
        )

        self.router.register_pipeline(config)
        assert self.router.get_pipeline_config(FileType.DATA) is not None

        self.router.unregister_pipeline(FileType.DATA)
        assert self.router.get_pipeline_config(FileType.DATA) is None


class TestPipelineConfig:
    """Test suite for PipelineConfig dataclass."""

    def test_pipeline_config_creation(self):
        """Test creating PipelineConfig object."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='test_dag',
            entity_name='test_entity',
            table_name='stg_test',
            required_columns=['col1', 'col2'],
        )

        assert config.dag_id == 'test_dag'
        assert config.entity_name == 'test_entity'
        assert len(config.required_columns) == 2

    def test_pipeline_config_validation_success(self):
        """Test valid PipelineConfig passes validation."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='valid_dag',
            entity_name='valid_entity',
            table_name='stg_valid',
            required_columns=['id'],
        )

        config.validate()  # Should not raise

    def test_pipeline_config_validation_missing_dag_id(self):
        """Test validation fails without dag_id."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='',
            entity_name='entity',
            table_name='stg_entity',
            required_columns=['id'],
        )

        with pytest.raises(ValueError):
            config.validate()

    def test_pipeline_config_validation_missing_entity_name(self):
        """Test validation fails without entity_name."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='test_dag',
            entity_name='',
            table_name='stg_test',
            required_columns=['id'],
        )

        with pytest.raises(ValueError):
            config.validate()

    def test_pipeline_config_with_processing_mode(self):
        """Test PipelineConfig with different processing modes."""
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='test_dag',
            entity_name='test',
            table_name='stg_test',
            required_columns=['id'],
            processing_mode=ProcessingMode.BATCH,
        )

        assert config.processing_mode == ProcessingMode.BATCH


class TestFileTypeEnum:
    """Test suite for FileType enumeration."""

    def test_file_type_values(self):
        """Test FileType enum has expected values."""
        assert FileType.DATA.value == 'data'
        assert FileType.METADATA.value == 'metadata'
        assert FileType.LOGS.value == 'logs'
        assert FileType.UNKNOWN.value == 'unknown'

    def test_file_type_comparison(self):
        """Test FileType enum comparison."""
        assert FileType.DATA == FileType.DATA
        assert FileType.DATA != FileType.METADATA


class TestProcessingModeEnum:
    """Test suite for ProcessingMode enumeration."""

    def test_processing_mode_values(self):
        """Test ProcessingMode enum has expected values."""
        assert ProcessingMode.DAILY.value == 'daily'
        assert ProcessingMode.ONDEMAND.value == 'ondemand'
        assert ProcessingMode.BATCH.value == 'batch'
        assert ProcessingMode.RECOVERY.value == 'recovery'


__all__ = [
    'TestDAGRouter',
    'TestPipelineConfig',
    'TestFileTypeEnum',
    'TestProcessingModeEnum',
]

