"""
Resource Configuration Module

Provides utilities for optimizing Apache Beam pipeline resources based on file sizes,
including automatic worker type selection, memory configuration, and Docker resource
recommendations.

Usage:
    from gcp_pipeline_beam.pipelines.beam.resource_config import (
        ResourceConfigurator,
        get_optimal_pipeline_options,
        get_docker_config,
    )

    # Auto-configure based on file size
    config = ResourceConfigurator()
    options = config.get_pipeline_options_for_file("gs://bucket/large-file.csv")

    # Or specify size directly
    options = get_optimal_pipeline_options(file_size_mb=500)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

try:
    from google.cloud import storage
    HAS_GCS = True
except ImportError:
    HAS_GCS = False

try:
    from apache_beam.options.pipeline_options import (
        PipelineOptions,
        GoogleCloudOptions,
        WorkerOptions,
        SetupOptions,
    )
    HAS_BEAM = True
except ImportError:
    HAS_BEAM = False


logger = logging.getLogger(__name__)


class FileSizeCategory(Enum):
    """File size categories for resource allocation."""
    SMALL = "small"       # < 100 MB
    MEDIUM = "medium"     # 100 MB - 1 GB
    LARGE = "large"       # 1 GB - 10 GB
    XLARGE = "xlarge"     # 10 GB - 100 GB
    SPLIT_REQUIRED = "split_required"  # > 100 GB


@dataclass
class WorkerConfig:
    """Configuration for Dataflow workers."""
    machine_type: str
    num_workers: int
    max_num_workers: int
    disk_size_gb: int
    disk_type: str = "pd-standard"
    memory_gb: float = 0.0
    cpu_cores: int = 0

    def __post_init__(self):
        """Set memory and CPU based on machine type."""
        machine_specs = {
            "n1-standard-1": (3.75, 1),
            "n1-standard-2": (7.5, 2),
            "n1-standard-4": (15, 4),
            "n1-standard-8": (30, 8),
            "n1-standard-16": (60, 16),
            "n1-highmem-2": (13, 2),
            "n1-highmem-4": (26, 4),
            "n1-highmem-8": (52, 8),
            "n1-highmem-16": (104, 16),
            "n1-highmem-32": (208, 32),
            "n2-standard-2": (8, 2),
            "n2-standard-4": (16, 4),
            "n2-standard-8": (32, 8),
            "n2-highmem-2": (16, 2),
            "n2-highmem-4": (32, 4),
            "n2-highmem-8": (64, 8),
        }
        if self.machine_type in machine_specs:
            self.memory_gb, self.cpu_cores = machine_specs[self.machine_type]


@dataclass
class DockerConfig:
    """Docker resource configuration."""
    memory_limit: str
    memory_reservation: str
    cpu_limit: str
    cpu_reservation: str
    environment: Dict[str, str]

    def to_compose_dict(self) -> Dict[str, Any]:
        """Convert to docker-compose format."""
        return {
            "deploy": {
                "resources": {
                    "limits": {
                        "cpus": self.cpu_limit,
                        "memory": self.memory_limit,
                    },
                    "reservations": {
                        "cpus": self.cpu_reservation,
                        "memory": self.memory_reservation,
                    }
                }
            },
            "environment": self.environment
        }


class ResourceConfigurator:
    """
    Automatic resource configurator for Apache Beam pipelines.

    Analyzes file sizes and recommends optimal resource configurations
    for both Dataflow (GCP) and Docker (local) execution.

    Example:
        >>> config = ResourceConfigurator()
        >>> options = config.get_pipeline_options_for_file("gs://bucket/file.csv")
        >>> docker = config.get_docker_config_for_size(500)  # 500 MB
    """

    # File size thresholds in MB
    SMALL_THRESHOLD_MB = 100
    MEDIUM_THRESHOLD_MB = 1000  # 1 GB
    LARGE_THRESHOLD_MB = 10000  # 10 GB
    XLARGE_THRESHOLD_MB = 100000  # 100 GB

    # Recommended batch sizes by category
    BATCH_SIZES = {
        FileSizeCategory.SMALL: 5000,
        FileSizeCategory.MEDIUM: 10000,
        FileSizeCategory.LARGE: 20000,
        FileSizeCategory.XLARGE: 50000,
    }

    def __init__(self, project_id: Optional[str] = None, region: str = "europe-west2"):
        """
        Initialize the resource configurator.

        Args:
            project_id: GCP project ID (for file size detection)
            region: GCP region for Dataflow jobs
        """
        self.project_id = project_id
        self.region = region
        self._storage_client = None

    @property
    def storage_client(self):
        """Lazy-load GCS client."""
        if self._storage_client is None and HAS_GCS:
            self._storage_client = storage.Client(project=self.project_id)
        return self._storage_client

    def get_file_size_mb(self, gcs_path: str) -> float:
        """
        Get file size in megabytes from GCS.

        Args:
            gcs_path: GCS path (gs://bucket/path/to/file)

        Returns:
            File size in MB
        """
        if not HAS_GCS:
            raise ImportError("google-cloud-storage is required for file size detection")

        blob = storage.Blob.from_string(gcs_path, client=self.storage_client)
        blob.reload()
        return blob.size / (1024 * 1024)

    def categorize_file_size(self, size_mb: float) -> FileSizeCategory:
        """
        Categorize file size for resource allocation.

        Args:
            size_mb: File size in megabytes

        Returns:
            FileSizeCategory enum value
        """
        if size_mb < self.SMALL_THRESHOLD_MB:
            return FileSizeCategory.SMALL
        elif size_mb < self.MEDIUM_THRESHOLD_MB:
            return FileSizeCategory.MEDIUM
        elif size_mb < self.LARGE_THRESHOLD_MB:
            return FileSizeCategory.LARGE
        elif size_mb < self.XLARGE_THRESHOLD_MB:
            return FileSizeCategory.XLARGE
        else:
            return FileSizeCategory.SPLIT_REQUIRED

    def get_worker_config(self, size_mb: float) -> WorkerConfig:
        """
        Get recommended Dataflow worker configuration.

        Args:
            size_mb: File size in megabytes

        Returns:
            WorkerConfig with optimal settings
        """
        category = self.categorize_file_size(size_mb)

        configs = {
            FileSizeCategory.SMALL: WorkerConfig(
                machine_type="n1-standard-2",
                num_workers=1,
                max_num_workers=3,
                disk_size_gb=50,
            ),
            FileSizeCategory.MEDIUM: WorkerConfig(
                machine_type="n1-standard-4",
                num_workers=2,
                max_num_workers=10,
                disk_size_gb=100,
            ),
            FileSizeCategory.LARGE: WorkerConfig(
                machine_type="n1-highmem-8",
                num_workers=4,
                max_num_workers=20,
                disk_size_gb=200,
            ),
            FileSizeCategory.XLARGE: WorkerConfig(
                machine_type="n1-highmem-16",
                num_workers=8,
                max_num_workers=50,
                disk_size_gb=500,
                disk_type="pd-ssd",
            ),
            FileSizeCategory.SPLIT_REQUIRED: WorkerConfig(
                machine_type="n1-highmem-32",
                num_workers=16,
                max_num_workers=100,
                disk_size_gb=1000,
                disk_type="pd-ssd",
            ),
        }

        return configs[category]

    def get_docker_config(self, size_mb: float) -> DockerConfig:
        """
        Get recommended Docker resource configuration.

        Args:
            size_mb: File size in megabytes

        Returns:
            DockerConfig with optimal settings
        """
        category = self.categorize_file_size(size_mb)
        batch_size = self.BATCH_SIZES.get(category, 10000)

        configs = {
            FileSizeCategory.SMALL: DockerConfig(
                memory_limit="4G",
                memory_reservation="2G",
                cpu_limit="2",
                cpu_reservation="1",
                environment={
                    "BEAM_DIRECT_NUM_WORKERS": "2",
                    "BEAM_DIRECT_RUNNING_MODE": "multi_threading",
                    "BATCH_SIZE": str(batch_size),
                }
            ),
            FileSizeCategory.MEDIUM: DockerConfig(
                memory_limit="8G",
                memory_reservation="4G",
                cpu_limit="4",
                cpu_reservation="2",
                environment={
                    "BEAM_DIRECT_NUM_WORKERS": "4",
                    "BEAM_DIRECT_RUNNING_MODE": "multi_threading",
                    "BATCH_SIZE": str(batch_size),
                }
            ),
            FileSizeCategory.LARGE: DockerConfig(
                memory_limit="16G",
                memory_reservation="8G",
                cpu_limit="8",
                cpu_reservation="4",
                environment={
                    "BEAM_DIRECT_NUM_WORKERS": "8",
                    "BEAM_DIRECT_RUNNING_MODE": "multi_threading",
                    "BATCH_SIZE": str(batch_size),
                }
            ),
            FileSizeCategory.XLARGE: DockerConfig(
                memory_limit="32G",
                memory_reservation="16G",
                cpu_limit="16",
                cpu_reservation="8",
                environment={
                    "BEAM_DIRECT_NUM_WORKERS": "16",
                    "BEAM_DIRECT_RUNNING_MODE": "multi_threading",
                    "BATCH_SIZE": str(batch_size),
                }
            ),
            FileSizeCategory.SPLIT_REQUIRED: DockerConfig(
                memory_limit="64G",
                memory_reservation="32G",
                cpu_limit="32",
                cpu_reservation="16",
                environment={
                    "BEAM_DIRECT_NUM_WORKERS": "32",
                    "BEAM_DIRECT_RUNNING_MODE": "multi_threading",
                    "BATCH_SIZE": str(batch_size),
                    "SPLIT_FILES": "true",
                }
            ),
        }

        return configs[category]

    def get_pipeline_options(self, size_mb: float, **kwargs) -> "PipelineOptions":
        """
        Get optimized PipelineOptions for Dataflow.

        Args:
            size_mb: File size in megabytes
            **kwargs: Additional pipeline options

        Returns:
            Configured PipelineOptions
        """
        if not HAS_BEAM:
            raise ImportError("apache-beam is required for pipeline options")

        worker_config = self.get_worker_config(size_mb)

        options = PipelineOptions(**kwargs)

        # Configure worker options
        worker_opts = options.view_as(WorkerOptions)
        worker_opts.machine_type = worker_config.machine_type
        worker_opts.num_workers = worker_config.num_workers
        worker_opts.max_num_workers = worker_config.max_num_workers
        worker_opts.disk_size_gb = worker_config.disk_size_gb

        if worker_config.disk_type == "pd-ssd":
            # Use SSD for large files
            worker_opts.disk_type = f"compute.googleapis.com/projects/{self.project_id}/zones/{self.region}-a/diskTypes/pd-ssd"

        # Configure GCP options
        gcp_opts = options.view_as(GoogleCloudOptions)
        if self.project_id:
            gcp_opts.project = self.project_id
        gcp_opts.region = self.region

        return options

    def get_pipeline_options_for_file(self, gcs_path: str, **kwargs) -> "PipelineOptions":
        """
        Get optimized PipelineOptions based on actual file size.

        Args:
            gcs_path: GCS path to the file
            **kwargs: Additional pipeline options

        Returns:
            Configured PipelineOptions
        """
        size_mb = self.get_file_size_mb(gcs_path)
        logger.info(f"File {gcs_path} is {size_mb:.2f} MB")

        category = self.categorize_file_size(size_mb)
        if category == FileSizeCategory.SPLIT_REQUIRED:
            logger.warning(
                f"File {gcs_path} is very large ({size_mb:.0f} MB). "
                "Consider splitting into smaller files for optimal performance."
            )

        return self.get_pipeline_options(size_mb, **kwargs)

    def get_recommendation_summary(self, size_mb: float) -> Dict[str, Any]:
        """
        Get a complete recommendation summary for a given file size.

        Args:
            size_mb: File size in megabytes

        Returns:
            Dictionary with all recommendations
        """
        category = self.categorize_file_size(size_mb)
        worker_config = self.get_worker_config(size_mb)
        docker_config = self.get_docker_config(size_mb)

        # Estimate processing time (rough estimate)
        # Assumes ~50 MB/s throughput with proper configuration
        estimated_minutes = max(1, size_mb / 50 / 60)

        # Estimate cost (rough estimate based on n1-standard-4 at ~$0.19/hr)
        hourly_rates = {
            "n1-standard-2": 0.095,
            "n1-standard-4": 0.19,
            "n1-standard-8": 0.38,
            "n1-highmem-8": 0.47,
            "n1-highmem-16": 0.95,
            "n1-highmem-32": 1.90,
        }
        hourly_rate = hourly_rates.get(worker_config.machine_type, 0.19)
        estimated_cost = (estimated_minutes / 60) * hourly_rate * worker_config.num_workers

        return {
            "file_size_mb": size_mb,
            "category": category.value,
            "should_split": category == FileSizeCategory.SPLIT_REQUIRED,
            "dataflow": {
                "machine_type": worker_config.machine_type,
                "num_workers": worker_config.num_workers,
                "max_num_workers": worker_config.max_num_workers,
                "disk_size_gb": worker_config.disk_size_gb,
                "disk_type": worker_config.disk_type,
                "memory_gb": worker_config.memory_gb,
                "cpu_cores": worker_config.cpu_cores,
            },
            "docker": {
                "memory_limit": docker_config.memory_limit,
                "cpu_limit": docker_config.cpu_limit,
                "environment": docker_config.environment,
            },
            "estimates": {
                "processing_minutes": round(estimated_minutes, 1),
                "cost_usd": round(estimated_cost, 2),
            },
            "recommendations": self._get_recommendations(category, size_mb),
        }

    def _get_recommendations(self, category: FileSizeCategory, size_mb: float) -> list[str]:
        """Get specific recommendations based on file size category."""
        recommendations = []

        if category == FileSizeCategory.SMALL:
            recommendations.append("Standard processing - no special handling needed")
            recommendations.append("Consider batching multiple small files together")

        elif category == FileSizeCategory.MEDIUM:
            recommendations.append("Ensure adequate worker memory for parsing overhead")
            recommendations.append("Use streaming writes to BigQuery")

        elif category == FileSizeCategory.LARGE:
            recommendations.append("Enable autoscaling with max_num_workers")
            recommendations.append("Consider using SSD disk type for faster I/O")
            recommendations.append("Monitor shuffle operations for bottlenecks")

        elif category == FileSizeCategory.XLARGE:
            recommendations.append("Use SSD disks for all workers")
            recommendations.append("Enable shuffle service for better performance")
            recommendations.append("Consider splitting file if processing is too slow")
            recommendations.append("Monitor for OOM errors and adjust worker type")

        elif category == FileSizeCategory.SPLIT_REQUIRED:
            recommendations.append(
                f"CRITICAL: File is {size_mb/1024:.1f} GB - split into smaller files"
            )
            recommendations.append("Recommended: Split into 1-5 GB chunks")
            recommendations.append("Use parallel processing across split files")
            recommendations.append("Consider incremental processing approach")

        return recommendations


# Convenience functions
def get_optimal_pipeline_options(
    file_size_mb: float,
    project_id: Optional[str] = None,
    region: str = "europe-west2",
    **kwargs
) -> "PipelineOptions":
    """
    Get optimized pipeline options for a given file size.

    Args:
        file_size_mb: File size in megabytes
        project_id: GCP project ID
        region: GCP region
        **kwargs: Additional pipeline options

    Returns:
        Configured PipelineOptions
    """
    config = ResourceConfigurator(project_id=project_id, region=region)
    return config.get_pipeline_options(file_size_mb, **kwargs)


def get_docker_config(file_size_mb: float) -> DockerConfig:
    """
    Get Docker configuration for a given file size.

    Args:
        file_size_mb: File size in megabytes

    Returns:
        DockerConfig with optimal settings
    """
    config = ResourceConfigurator()
    return config.get_docker_config(file_size_mb)


def print_resource_recommendations(file_size_mb: float) -> None:
    """
    Print resource recommendations for a given file size.

    Args:
        file_size_mb: File size in megabytes
    """
    config = ResourceConfigurator()
    summary = config.get_recommendation_summary(file_size_mb)

    print(f"\n{'='*60}")
    print(f"Resource Recommendations for {file_size_mb} MB file")
    print(f"{'='*60}")
    print(f"Category: {summary['category'].upper()}")

    if summary['should_split']:
        print(f"\n⚠️  WARNING: File should be split for optimal processing")

    print(f"\n📊 Dataflow Configuration:")
    for key, value in summary['dataflow'].items():
        print(f"   {key}: {value}")

    print(f"\n🐳 Docker Configuration:")
    print(f"   Memory: {summary['docker']['memory_limit']}")
    print(f"   CPU: {summary['docker']['cpu_limit']}")

    print(f"\n⏱️  Estimates:")
    print(f"   Processing Time: ~{summary['estimates']['processing_minutes']} minutes")
    print(f"   Estimated Cost: ~${summary['estimates']['cost_usd']}")

    print(f"\n💡 Recommendations:")
    for rec in summary['recommendations']:
        print(f"   • {rec}")

    print(f"{'='*60}\n")

