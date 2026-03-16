"""
Recovery management for point-in-time restoration and rollback.

Provides two implementations:
- RecoveryManager: In-memory checkpoints (fast, for short-lived processes)
- GCSRecoveryManager: GCS-persisted checkpoints (durable, survives worker restarts)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RecoveryPoint:
    """Represents a recovery point for state restoration."""
    checkpoint_name: str
    timestamp: str
    state: Dict[str, Any]
    malformed_records: List[Dict[str, Any]] = field(default_factory=list)


class RecoveryManager:
    """Manages recovery points and point-in-time restoration."""

    def __init__(self):
        """Initialize the recovery manager."""
        self.recovery_points: Dict[str, RecoveryPoint] = {}

    def create_recovery_point(
        self,
        checkpoint_name: str,
        state: Dict[str, Any],
        malformed_records: List[Any] = None
    ) -> RecoveryPoint:
        """
        Create recovery point before deletion.

        Args:
            checkpoint_name: Name of the checkpoint
            state: Current state to save
            malformed_records: List of malformed records

        Returns:
            RecoveryPoint instance
        """
        records_data = []
        if malformed_records:
            records_data = [
                {
                    "id": m.record_id,
                    "type": m.entity_type,
                    "reasons": m.reasons,
                    "checksum": m.checksum
                }
                for m in malformed_records
            ]

        recovery_point = RecoveryPoint(
            checkpoint_name=checkpoint_name,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            state=state,
            malformed_records=records_data
        )

        self.recovery_points[checkpoint_name] = recovery_point

        logger.info("Recovery point created: %s", checkpoint_name)

        return recovery_point

    def restore_from_recovery_point(
        self,
        checkpoint_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Restore from recovery point.

        Args:
            checkpoint_name: Name of checkpoint to restore

        Returns:
            Restored state or None if checkpoint not found
        """
        if checkpoint_name not in self.recovery_points:
            logger.error("Recovery point not found: %s", checkpoint_name)
            return None

        recovery_point = self.recovery_points[checkpoint_name]

        logger.info("Restored from checkpoint: %s", checkpoint_name)

        return {
            "checkpoint": checkpoint_name,
            "timestamp": recovery_point.timestamp,
            "state": recovery_point.state,
            "malformed_records": recovery_point.malformed_records
        }

    def list_recovery_points(self) -> List[str]:
        """Get list of available recovery points."""
        return list(self.recovery_points.keys())

    def get_recovery_point(
        self,
        checkpoint_name: str
    ) -> Optional[RecoveryPoint]:
        """Get a specific recovery point."""
        return self.recovery_points.get(checkpoint_name)

    def delete_recovery_point(self, checkpoint_name: str) -> bool:
        """
        Delete a recovery point.

        Args:
            checkpoint_name: Name of checkpoint to delete

        Returns:
            True if deleted, False if not found
        """
        if checkpoint_name in self.recovery_points:
            del self.recovery_points[checkpoint_name]
            logger.info("Recovery point deleted: %s", checkpoint_name)
            return True

        logger.warning("Recovery point not found for deletion: %s",
                      checkpoint_name)
        return False


class GCSRecoveryManager(RecoveryManager):
    """
    Recovery manager that persists checkpoints to Google Cloud Storage.

    Survives worker restarts and process failures — suitable for
    long-running Dataflow jobs and Airflow tasks.

    Checkpoints are stored as JSON files at:
        gs://{bucket}/{prefix}/{checkpoint_name}.json

    Example:
        >>> manager = GCSRecoveryManager(
        ...     bucket_name="my-project-generic-int-temp",
        ...     prefix="recovery_points/run_123"
        ... )
        >>> manager.create_recovery_point("after_validation", {"records_valid": 500})
        >>> # Worker restarts...
        >>> manager = GCSRecoveryManager(bucket_name=..., prefix=...)
        >>> state = manager.restore_from_recovery_point("after_validation")
    """

    def __init__(self, bucket_name: str, prefix: str = "recovery_points"):
        """
        Initialize GCS-backed recovery manager.

        Args:
            bucket_name: GCS bucket name (without gs:// prefix)
            prefix: Path prefix within bucket for checkpoint files
        """
        super().__init__()
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip("/")

    def _gcs_path(self, checkpoint_name: str) -> str:
        """Build the GCS object path for a checkpoint."""
        return f"{self.prefix}/{checkpoint_name}.json"

    def _get_bucket(self):
        """Lazy-load GCS bucket client."""
        from google.cloud import storage
        client = storage.Client()
        return client.bucket(self.bucket_name)

    def create_recovery_point(
        self,
        checkpoint_name: str,
        state: Dict[str, Any],
        malformed_records: List[Any] = None
    ) -> RecoveryPoint:
        """
        Create recovery point and persist to GCS.

        Args:
            checkpoint_name: Name of the checkpoint
            state: Current state to save
            malformed_records: List of malformed records

        Returns:
            RecoveryPoint instance
        """
        recovery_point = super().create_recovery_point(
            checkpoint_name, state, malformed_records
        )

        # Persist to GCS
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(self._gcs_path(checkpoint_name))
            blob.upload_from_string(
                json.dumps(asdict(recovery_point), default=str),
                content_type="application/json",
            )
            logger.info(
                "Recovery point persisted to gs://%s/%s",
                self.bucket_name, self._gcs_path(checkpoint_name)
            )
        except Exception as e:
            logger.error(
                "Failed to persist recovery point %s to GCS: %s",
                checkpoint_name, e
            )

        return recovery_point

    def restore_from_recovery_point(
        self,
        checkpoint_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Restore from recovery point, loading from GCS if not in memory.

        Args:
            checkpoint_name: Name of checkpoint to restore

        Returns:
            Restored state or None if checkpoint not found
        """
        # Try in-memory first
        if checkpoint_name in self.recovery_points:
            return super().restore_from_recovery_point(checkpoint_name)

        # Load from GCS
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(self._gcs_path(checkpoint_name))

            if not blob.exists():
                logger.error("Recovery point not found in GCS: %s", checkpoint_name)
                return None

            data = json.loads(blob.download_as_text())

            # Reconstruct RecoveryPoint and cache in memory
            recovery_point = RecoveryPoint(
                checkpoint_name=data["checkpoint_name"],
                timestamp=data["timestamp"],
                state=data["state"],
                malformed_records=data.get("malformed_records", []),
            )
            self.recovery_points[checkpoint_name] = recovery_point

            logger.info(
                "Recovery point restored from gs://%s/%s",
                self.bucket_name, self._gcs_path(checkpoint_name)
            )

            return {
                "checkpoint": checkpoint_name,
                "timestamp": recovery_point.timestamp,
                "state": recovery_point.state,
                "malformed_records": recovery_point.malformed_records,
            }

        except Exception as e:
            logger.error(
                "Failed to restore recovery point %s from GCS: %s",
                checkpoint_name, e
            )
            return None

    def delete_recovery_point(self, checkpoint_name: str) -> bool:
        """
        Delete a recovery point from both memory and GCS.

        Args:
            checkpoint_name: Name of checkpoint to delete

        Returns:
            True if deleted, False if not found
        """
        deleted = super().delete_recovery_point(checkpoint_name)

        # Also delete from GCS
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(self._gcs_path(checkpoint_name))
            if blob.exists():
                blob.delete()
                logger.info(
                    "Recovery point deleted from gs://%s/%s",
                    self.bucket_name, self._gcs_path(checkpoint_name)
                )
                return True
        except Exception as e:
            logger.error(
                "Failed to delete recovery point %s from GCS: %s",
                checkpoint_name, e
            )

        return deleted

    def list_recovery_points(self) -> List[str]:
        """
        List recovery points from both memory and GCS.

        Returns:
            Combined list of checkpoint names
        """
        names = set(super().list_recovery_points())

        # Also list from GCS
        try:
            bucket = self._get_bucket()
            prefix = f"{self.prefix}/"
            blobs = bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                name = blob.name.replace(prefix, "").replace(".json", "")
                if name:
                    names.add(name)
        except Exception as e:
            logger.error("Failed to list recovery points from GCS: %s", e)

        return sorted(names)

