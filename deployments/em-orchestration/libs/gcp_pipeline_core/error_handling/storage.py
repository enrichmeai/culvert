"""
Error storage backends for persisting error records.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, TYPE_CHECKING
import logging

from ..utilities.logging import get_logger

if TYPE_CHECKING:
    from .models import PipelineError

logger = get_logger(__name__)


class ErrorStorageBackend(ABC):
    """Abstract base class for error storage backends"""

    @abstractmethod
    def store_error(self, error: 'PipelineError') -> bool:
        """Store error record"""
        pass

    @abstractmethod
    def retrieve_errors(self, run_id: str) -> List['PipelineError']:
        """Retrieve errors for a run"""
        pass

    @abstractmethod
    def retrieve_retryable(self) -> List['PipelineError']:
        """Retrieve all retryable errors"""
        pass


class InMemoryErrorStorage(ErrorStorageBackend):
    """In-memory error storage (for testing)"""

    def __init__(self):
        self.errors: Dict[str, List['PipelineError']] = {}

    def store_error(self, error: 'PipelineError') -> bool:
        if error.run_id not in self.errors:
            self.errors[error.run_id] = []
        self.errors[error.run_id].append(error)
        return True

    def retrieve_errors(self, run_id: str) -> List['PipelineError']:
        return self.errors.get(run_id, [])

    def retrieve_retryable(self) -> List['PipelineError']:
        all_errors = []
        for errors in self.errors.values():
            all_errors.extend(errors)
        return [e for e in all_errors if not e.resolved]


class GCSErrorStorage(ErrorStorageBackend):
    """Error storage in GCS (production)"""

    def __init__(self, gcs_bucket: str, gcs_prefix: str = "error_logs"):
        self.gcs_bucket = gcs_bucket
        self.gcs_prefix = gcs_prefix

    def store_error(self, error: 'PipelineError') -> bool:
        """Store error as JSON file in GCS"""
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(self.gcs_bucket)

            path = (f"{self.gcs_prefix}/{error.run_id}/"
                   f"{error.error_id}.json")
            blob = bucket.blob(path)
            blob.upload_from_string(error.to_json())

            logger.info(f"Stored error {error.error_id} to gs://{self.gcs_bucket}/{path}")
            return True
        except Exception as e:
            logger.error(f"Failed to store error in GCS: {e}")
            return False

    def retrieve_errors(self, run_id: str) -> List['PipelineError']:
        """Retrieve errors for a run from GCS"""
        from .models import PipelineError
        from google.cloud import storage
        
        errors = []
        try:
            client = storage.Client()
            bucket = client.bucket(self.gcs_bucket)
            prefix = f"{self.gcs_prefix}/{run_id}/"
            
            blobs = bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                if blob.name.endswith(".json"):
                    content = blob.download_as_text()
                    errors.append(PipelineError.from_json(content))
            
            logger.info(f"Retrieved {len(errors)} errors for run {run_id} from GCS")
        except Exception as e:
            logger.error(f"Failed to retrieve errors from GCS: {e}")
            
        return errors

    def retrieve_retryable(self) -> List['PipelineError']:
        """Retrieve all retryable errors from GCS"""
        from .models import PipelineError
        from google.cloud import storage
        
        errors = []
        try:
            client = storage.Client()
            bucket = client.bucket(self.gcs_bucket)
            
            # Note: This could be expensive for large buckets
            blobs = bucket.list_blobs(prefix=self.gcs_prefix)
            for blob in blobs:
                if blob.name.endswith(".json"):
                    content = blob.download_as_text()
                    error = PipelineError.from_json(content)
                    if not error.resolved:
                        errors.append(error)
            
            logger.info(f"Retrieved {len(errors)} retryable errors from GCS")
        except Exception as e:
            logger.error(f"Failed to retrieve retryable errors from GCS: {e}")
            
        return errors

