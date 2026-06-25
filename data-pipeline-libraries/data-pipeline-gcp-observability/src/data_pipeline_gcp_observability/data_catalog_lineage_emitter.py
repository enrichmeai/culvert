"""DataCatalogLineageEmitter — LineageEmitter backed by Google Data Catalog.

Java sibling:
  data-pipeline-libraries-java/data-pipeline-gcp-observability-java/src/main/java/
  com/enrichmeai/culvert/gcp/observability/DataCatalogLineageEmitter.java

Imports ``google.cloud.datacatalog_v1`` lazily so the module can be imported
offline / in unit-test environments.  Pass a mock ``DataCatalogClient`` in
tests; never call the real API.

Sprint-19 / T19.2 — issue #125.
"""

from __future__ import annotations

import logging
from typing import Any

from data_pipeline_core.lineage.events import LineageEvent

logger = logging.getLogger(__name__)


class DataCatalogLineageEmitter:
    """LineageEmitter that writes lineage events as Data Catalog tags.

    Mirrors Java ``DataCatalogLineageEmitter`` (line 55).

    Each ``LineageEvent`` becomes one tag attached to the configured Data
    Catalog entry.  The tag's fields mirror the four sub-dicts of
    ``LineageEvent`` (source, pipeline, destination, audit), flattened to
    scalar string values — mirrors Java ``flatten()`` helper (line 137).

    Construction
    ------------
    - ``DataCatalogLineageEmitter(client, entry_name, tag_template)``
      Primary.  Mirrors Java constructor (line 77).  Caller owns the
      credential lifecycle; pass a ``MagicMock()`` for the client in tests.

    Lifecycle
    ---------
    Implements context-manager protocol and ``close()``.  Mirrors Java
    ``AutoCloseable.close()`` (line 128).
    """

    def __init__(self, client: Any, entry_name: str, tag_template: str) -> None:
        """Inject a pre-built DataCatalogClient and entry / template identifiers.

        Args:
            client:       DataCatalogClient (real or mock).  Required.
            entry_name:   Fully-qualified Data Catalog entry name
                          (``projects/{p}/locations/{l}/entryGroups/{g}/entries/{e}``).
                          Required.
            tag_template: Fully-qualified tag template name
                          (``projects/{p}/locations/{l}/tagTemplates/{t}``).
                          Required.

        Raises:
            TypeError: if any argument is None.
        """
        if client is None:
            raise TypeError("client must not be None")
        if entry_name is None:
            raise TypeError("entry_name must not be None")
        if tag_template is None:
            raise TypeError("tag_template must not be None")
        self._client = client
        self._entry_name = entry_name
        self._tag_template = tag_template

    # ------------------------------------------------------------------
    # LineageEmitter Protocol
    # ------------------------------------------------------------------

    def emit(self, event: LineageEvent) -> None:
        """Emit one lineage event as a Data Catalog tag — mirrors Java emit() (line 95).

        The event's sub-dicts are flattened to scalar string fields and written
        as a Data Catalog tag on ``entry_name`` using ``tag_template``.

        If the underlying Data Catalog call raises, the exception propagates to
        the caller (mirrors Java — exceptions are not swallowed here, unlike
        ``StageMetricsHook``).

        Args:
            event: The lineage event to emit.  Must not be None.

        Raises:
            TypeError: if ``event`` is None.
        """
        if event is None:
            raise TypeError("event must not be None")

        fields = self._flatten(event)

        # Lazy import — avoids hard dependency at module import time.
        try:
            from google.cloud import datacatalog_v1  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "google-cloud-datacatalog is required for DataCatalogLineageEmitter.emit(). "
                "Install it with: pip install google-cloud-datacatalog"
            ) from exc

        tag = datacatalog_v1.Tag(template=self._tag_template)
        for field_name, str_value in fields.items():
            tag.fields[field_name] = datacatalog_v1.TagField(
                string_value=str_value
            )

        request = datacatalog_v1.CreateTagRequest(
            parent=self._entry_name,
            tag=tag,
        )
        self._client.create_tag(request=request)
        logger.debug("emitted lineage tag for entry %s", self._entry_name)

    # ------------------------------------------------------------------
    # Accessors / lifecycle
    # ------------------------------------------------------------------

    @property
    def entry_name(self) -> str:
        """Data Catalog entry name lineage tags are attached to — mirrors Java entryName() (line 117)."""
        return self._entry_name

    @property
    def tag_template(self) -> str:
        """Tag template the emitted tags reference — mirrors Java tagTemplate() (line 122)."""
        return self._tag_template

    def close(self) -> None:
        """Close the underlying DataCatalogClient — mirrors Java close() (line 128)."""
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> "DataCatalogLineageEmitter":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten(event: LineageEvent) -> dict[str, str]:
        """Flatten a LineageEvent into scalar string fields.

        Mirrors Java ``flatten()`` helper (line 137).  ``total=False``
        TypedDicts mean sub-dicts may be absent; absent keys are skipped.
        """
        out: dict[str, str] = {}

        source = event.get("source")
        if source:
            if "type" in source:
                out["source_type"] = str(source["type"])
            if "uri" in source:
                out["source_uri"] = str(source["uri"])

        pipeline = event.get("pipeline")
        if pipeline:
            if "run_id" in pipeline:
                out["run_id"] = str(pipeline["run_id"])
            if "pipeline_name" in pipeline:
                out["pipeline_name"] = str(pipeline["pipeline_name"])
            if "stage" in pipeline:
                out["stage"] = str(pipeline["stage"])
            if "started_at" in pipeline:
                out["started_at"] = str(pipeline["started_at"])
            if "completed_at" in pipeline:
                out["completed_at"] = str(pipeline["completed_at"])

        destination = event.get("destination")
        if destination:
            if "type" in destination:
                out["destination_type"] = str(destination["type"])
            if "uri" in destination:
                out["destination_uri"] = str(destination["uri"])

        audit = event.get("audit")
        if audit:
            out["audit"] = str(audit)

        return out
