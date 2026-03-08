"""
Unit tests for Resource Configuration Module.

Tests the ResourceConfigurator class and utility functions for
automatic resource allocation based on file sizes.
"""

import pytest
from unittest.mock import Mock, patch

from gcp_pipeline_beam.pipelines.beam.resource_config import (
    ResourceConfigurator,
    WorkerConfig,
    DockerConfig,
    FileSizeCategory,
    get_optimal_pipeline_options,
    get_docker_config,
)


class TestFileSizeCategory:
    """Tests for file size categorization."""

    def test_small_file_categorization(self):
        """Files under 100 MB should be categorized as SMALL."""
        config = ResourceConfigurator()

        assert config.categorize_file_size(10) == FileSizeCategory.SMALL
        assert config.categorize_file_size(50) == FileSizeCategory.SMALL
        assert config.categorize_file_size(99) == FileSizeCategory.SMALL

    def test_medium_file_categorization(self):
        """Files between 100 MB and 1 GB should be MEDIUM."""
        config = ResourceConfigurator()

        assert config.categorize_file_size(100) == FileSizeCategory.MEDIUM
        assert config.categorize_file_size(500) == FileSizeCategory.MEDIUM
        assert config.categorize_file_size(999) == FileSizeCategory.MEDIUM

    def test_large_file_categorization(self):
        """Files between 1 GB and 10 GB should be LARGE."""
        config = ResourceConfigurator()

        assert config.categorize_file_size(1000) == FileSizeCategory.LARGE
        assert config.categorize_file_size(5000) == FileSizeCategory.LARGE
        assert config.categorize_file_size(9999) == FileSizeCategory.LARGE

    def test_xlarge_file_categorization(self):
        """Files between 10 GB and 100 GB should be XLARGE."""
        config = ResourceConfigurator()

        assert config.categorize_file_size(10000) == FileSizeCategory.XLARGE
        assert config.categorize_file_size(50000) == FileSizeCategory.XLARGE
        assert config.categorize_file_size(99999) == FileSizeCategory.XLARGE

    def test_split_required_categorization(self):
        """Files over 100 GB should require splitting."""
        config = ResourceConfigurator()

        assert config.categorize_file_size(100000) == FileSizeCategory.SPLIT_REQUIRED
        assert config.categorize_file_size(500000) == FileSizeCategory.SPLIT_REQUIRED


class TestWorkerConfig:
    """Tests for WorkerConfig dataclass."""

    def test_worker_config_creation(self):
        """Worker configs should be created with correct attributes."""
        config = WorkerConfig(
            machine_type="n1-standard-4",
            num_workers=2,
            max_num_workers=10,
            disk_size_gb=100,
        )

        assert config.machine_type == "n1-standard-4"
        assert config.num_workers == 2
        assert config.max_num_workers == 10
        assert config.disk_size_gb == 100

    def test_worker_config_memory_detection(self):
        """Worker config should auto-detect memory from machine type."""
        config = WorkerConfig(
            machine_type="n1-standard-4",
            num_workers=1,
            max_num_workers=3,
            disk_size_gb=50,
        )

        assert config.memory_gb == 15
        assert config.cpu_cores == 4

    def test_highmem_worker_config(self):
        """High-memory machine types should have correct memory."""
        config = WorkerConfig(
            machine_type="n1-highmem-8",
            num_workers=4,
            max_num_workers=20,
            disk_size_gb=200,
        )

        assert config.memory_gb == 52
        assert config.cpu_cores == 8


class TestDockerConfig:
    """Tests for DockerConfig dataclass."""

    def test_docker_config_creation(self):
        """Docker configs should be created correctly."""
        config = DockerConfig(
            memory_limit="8G",
            memory_reservation="4G",
            cpu_limit="4",
            cpu_reservation="2",
            environment={"BEAM_DIRECT_NUM_WORKERS": "4"},
        )

        assert config.memory_limit == "8G"
        assert config.cpu_limit == "4"

    def test_docker_config_to_compose(self):
        """Docker config should convert to compose format."""
        config = DockerConfig(
            memory_limit="8G",
            memory_reservation="4G",
            cpu_limit="4",
            cpu_reservation="2",
            environment={"TEST": "value"},
        )

        compose = config.to_compose_dict()

        assert compose["deploy"]["resources"]["limits"]["memory"] == "8G"
        assert compose["deploy"]["resources"]["limits"]["cpus"] == "4"
        assert compose["environment"]["TEST"] == "value"


class TestResourceConfigurator:
    """Tests for ResourceConfigurator class."""

    def test_get_worker_config_small_file(self):
        """Small files should get minimal worker config."""
        config = ResourceConfigurator()
        worker = config.get_worker_config(50)  # 50 MB

        assert worker.machine_type == "n1-standard-2"
        assert worker.num_workers == 1
        assert worker.max_num_workers == 3

    def test_get_worker_config_medium_file(self):
        """Medium files should get standard config."""
        config = ResourceConfigurator()
        worker = config.get_worker_config(500)  # 500 MB

        assert worker.machine_type == "n1-standard-4"
        assert worker.num_workers == 2
        assert worker.max_num_workers == 10

    def test_get_worker_config_large_file(self):
        """Large files should get high-memory config."""
        config = ResourceConfigurator()
        worker = config.get_worker_config(5000)  # 5 GB

        assert worker.machine_type == "n1-highmem-8"
        assert worker.num_workers == 4
        assert worker.max_num_workers == 20

    def test_get_worker_config_xlarge_file(self):
        """XLarge files should get maximum config with SSD."""
        config = ResourceConfigurator()
        worker = config.get_worker_config(50000)  # 50 GB

        assert worker.machine_type == "n1-highmem-16"
        assert worker.disk_type == "pd-ssd"
        assert worker.disk_size_gb == 500

    def test_get_docker_config_small_file(self):
        """Small files should get minimal Docker resources."""
        config = ResourceConfigurator()
        docker = config.get_docker_config(50)  # 50 MB

        assert docker.memory_limit == "4G"
        assert docker.cpu_limit == "2"
        assert docker.environment["BEAM_DIRECT_NUM_WORKERS"] == "2"

    def test_get_docker_config_large_file(self):
        """Large files should get high Docker resources."""
        config = ResourceConfigurator()
        docker = config.get_docker_config(5000)  # 5 GB

        assert docker.memory_limit == "16G"
        assert docker.cpu_limit == "8"
        assert docker.environment["BEAM_DIRECT_NUM_WORKERS"] == "8"

    def test_batch_size_scaling(self):
        """Batch sizes should scale with file size."""
        config = ResourceConfigurator()

        small_docker = config.get_docker_config(50)
        large_docker = config.get_docker_config(5000)

        small_batch = int(small_docker.environment["BATCH_SIZE"])
        large_batch = int(large_docker.environment["BATCH_SIZE"])

        assert large_batch > small_batch

    def test_recommendation_summary(self):
        """Summary should include all recommendation sections."""
        config = ResourceConfigurator()
        summary = config.get_recommendation_summary(500)  # 500 MB

        assert "file_size_mb" in summary
        assert "category" in summary
        assert "dataflow" in summary
        assert "docker" in summary
        assert "estimates" in summary
        assert "recommendations" in summary

        assert summary["file_size_mb"] == 500
        assert summary["category"] == "medium"

    def test_split_required_recommendation(self):
        """Very large files should get split recommendation."""
        config = ResourceConfigurator()
        summary = config.get_recommendation_summary(150000)  # 150 GB

        assert summary["should_split"] is True
        assert any("split" in r.lower() for r in summary["recommendations"])


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_docker_config_function(self):
        """get_docker_config function should return valid config."""
        docker = get_docker_config(500)

        assert isinstance(docker, DockerConfig)
        assert docker.memory_limit is not None

    @patch('gcp_pipeline_beam.pipelines.beam.resource_config.HAS_BEAM', True)
    def test_get_optimal_pipeline_options(self):
        """get_optimal_pipeline_options should return valid options."""
        # Skip if beam not available
        try:
            from apache_beam.options.pipeline_options import PipelineOptions

            options = get_optimal_pipeline_options(
                file_size_mb=500,
                project_id="test-project",
                region="europe-west2"
            )

            assert options is not None
        except ImportError:
            pytest.skip("apache-beam not installed")


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_file_size(self):
        """Zero file size should be categorized as SMALL."""
        config = ResourceConfigurator()
        assert config.categorize_file_size(0) == FileSizeCategory.SMALL

    def test_exact_threshold_100mb(self):
        """100 MB should be MEDIUM (at threshold)."""
        config = ResourceConfigurator()
        assert config.categorize_file_size(100) == FileSizeCategory.MEDIUM

    def test_exact_threshold_1gb(self):
        """1 GB should be LARGE (at threshold)."""
        config = ResourceConfigurator()
        assert config.categorize_file_size(1000) == FileSizeCategory.LARGE

    def test_exact_threshold_10gb(self):
        """10 GB should be XLARGE (at threshold)."""
        config = ResourceConfigurator()
        assert config.categorize_file_size(10000) == FileSizeCategory.XLARGE

    def test_exact_threshold_100gb(self):
        """100 GB should require splitting (at threshold)."""
        config = ResourceConfigurator()
        assert config.categorize_file_size(100000) == FileSizeCategory.SPLIT_REQUIRED

    def test_very_small_file(self):
        """Very small files (KB) should work."""
        config = ResourceConfigurator()
        assert config.categorize_file_size(0.001) == FileSizeCategory.SMALL

    def test_fractional_file_sizes(self):
        """Fractional MB values should work."""
        config = ResourceConfigurator()
        docker = config.get_docker_config(99.9)

        assert docker is not None
        assert docker.memory_limit == "4G"  # Still SMALL category

