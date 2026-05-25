"""Split-file reassembly for mainframe extracts.

Mainframe extract jobs often chunk a single logical entity's file into multiple
parts because the mainframe's network or operational batch policy forbids files
above a certain size. Typical naming convention:

    customers.20260417.001of005.csv
    customers.20260417.002of005.csv
    customers.20260417.003of005.csv
    customers.20260417.004of005.csv
    customers.20260417.005of005.csv

Each chunk has its own HDR and TRL envelope. Each `.ok` file signals that
one chunk is complete. The pipeline must:

1. Wait for all declared parts (and their `.ok` markers) to land.
2. Return the ordered list of chunk URIs.
3. Hand off to ``HDRTRLParser`` to parse each chunk in sequence.

``SplitFileHandler`` encapsulates the first two steps.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from gcp_pipeline_core.clients import GCSClient

log = logging.getLogger(__name__)

DEFAULT_PART_PATTERN = (
    r"^(?P<prefix>.+?)\.(?P<ds>\d{8})\.(?P<part>\d{3})of(?P<total>\d{3})\.csv$"
)


@dataclass(frozen=True)
class SplitFilePart:
    """A single chunk identified during a split-file scan."""

    uri: str
    part_number: int
    total_parts: int
    ok_uri: Optional[str]

    @property
    def is_ready(self) -> bool:
        """True once the matching ``.ok`` sentinel has arrived."""
        return self.ok_uri is not None


@dataclass(frozen=True)
class SplitFileSet:
    """A complete, ordered set of split-file parts."""

    prefix: str
    extract_date: str
    total_parts: int
    parts: Tuple[SplitFilePart, ...]

    @property
    def uris(self) -> Tuple[str, ...]:
        return tuple(p.uri for p in self.parts)

    @property
    def complete(self) -> bool:
        return (
            len(self.parts) == self.total_parts
            and all(p.is_ready for p in self.parts)
        )


class SplitFileTimeoutError(TimeoutError):
    """Raised when a split-file set does not complete within the budget."""


class SplitFileHandler:
    """Wait for and enumerate a set of split mainframe extract files.

    Typical usage inside an ingestion pipeline:

    >>> handler = SplitFileHandler(bucket="generic-landing")
    >>> split_set = handler.wait_for_complete_set(
    ...     prefix="customers",
    ...     extract_date="20260417",
    ...     timeout_seconds=900,
    ... )
    >>> for uri in split_set.uris:
    ...     process(uri)

    The handler is **stateless**; call it on demand from a Beam or Airflow
    operator. It delegates all GCS traffic to ``gcp_pipeline_core.clients.GCSClient``.
    """

    def __init__(
        self,
        bucket: str,
        gcs_client: Optional[GCSClient] = None,
        part_pattern: str = DEFAULT_PART_PATTERN,
        ok_suffix: str = ".ok",
        poll_interval_seconds: float = 15.0,
    ) -> None:
        self.bucket = bucket
        self.gcs = gcs_client or GCSClient()
        self._part_re = re.compile(part_pattern)
        self.ok_suffix = ok_suffix
        self.poll_interval_seconds = poll_interval_seconds

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def scan(self, prefix: str, extract_date: str) -> SplitFileSet:
        """List the current state of split-file parts for a given prefix+date.

        Does not block; returns whatever has landed so far.
        """
        csv_uris = self._list_matching_csvs(prefix, extract_date)
        ok_uris = set(self._list_matching_oks(prefix, extract_date))

        parts: List[SplitFilePart] = []
        total_declared: Optional[int] = None
        for uri in sorted(csv_uris):
            m = self._part_re.match(uri.rsplit("/", 1)[-1])
            if not m:
                log.debug("skipping non-matching object: %s", uri)
                continue
            part_no = int(m.group("part"))
            total = int(m.group("total"))
            total_declared = total_declared or total
            ok_uri = f"{uri[:-4]}{self.ok_suffix}"
            parts.append(
                SplitFilePart(
                    uri=uri,
                    part_number=part_no,
                    total_parts=total,
                    ok_uri=ok_uri if ok_uri in ok_uris else None,
                )
            )
        parts.sort(key=lambda p: p.part_number)
        return SplitFileSet(
            prefix=prefix,
            extract_date=extract_date,
            total_parts=total_declared or 0,
            parts=tuple(parts),
        )

    def wait_for_complete_set(
        self,
        prefix: str,
        extract_date: str,
        timeout_seconds: float = 900.0,
    ) -> SplitFileSet:
        """Block until every declared part and its ``.ok`` sentinel has landed.

        Polls every ``poll_interval_seconds``. Raises ``SplitFileTimeoutError``
        if ``timeout_seconds`` passes before completion.
        """
        deadline = time.monotonic() + timeout_seconds
        last: Optional[SplitFileSet] = None
        while time.monotonic() < deadline:
            last = self.scan(prefix, extract_date)
            if last.complete and last.total_parts > 0:
                log.info(
                    "split set complete: prefix=%s date=%s parts=%d",
                    prefix, extract_date, last.total_parts,
                )
                return last
            log.debug(
                "waiting for split set: prefix=%s date=%s have=%d/%d",
                prefix, extract_date, len(last.parts), last.total_parts,
            )
            time.sleep(self.poll_interval_seconds)

        raise SplitFileTimeoutError(
            f"Split-file set not complete after {timeout_seconds}s: "
            f"prefix={prefix} date={extract_date} "
            f"have={len(last.parts) if last else 0}/"
            f"{last.total_parts if last else '?'}"
        )

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _list_matching_csvs(self, prefix: str, extract_date: str) -> Iterable[str]:
        glob_prefix = f"{prefix}.{extract_date}."
        return [
            f"gs://{self.bucket}/{name}"
            for name in self.gcs.list_blobs(self.bucket, prefix=glob_prefix)
            if name.endswith(".csv")
        ]

    def _list_matching_oks(self, prefix: str, extract_date: str) -> Iterable[str]:
        glob_prefix = f"{prefix}.{extract_date}."
        return [
            f"gs://{self.bucket}/{name}"
            for name in self.gcs.list_blobs(self.bucket, prefix=glob_prefix)
            if name.endswith(self.ok_suffix)
        ]


__all__ = [
    "DEFAULT_PART_PATTERN",
    "SplitFilePart",
    "SplitFileSet",
    "SplitFileHandler",
    "SplitFileTimeoutError",
]
