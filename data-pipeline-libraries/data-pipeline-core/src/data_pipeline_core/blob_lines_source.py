"""``BlobLinesSource`` — records from JSON-lines or CSV objects in any ``BlobStore`` (#13)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterator, Mapping, Sequence, Union

_FORMATS = ("jsonl", "csv")


class BlobLinesSource:
    """A ``Source`` of mapping records read from one or more objects in a ``BlobStore``.

    - ``format="jsonl"``: one JSON object per line; blank lines are skipped.
      A line that is not a JSON object raises ``ValueError`` naming the
      object and line number.
    - ``format="csv"``: a header row, then one record per row (all values
      strings). A row with more fields than the header raises ``ValueError``
      naming the object and line; a shorter row has ``None`` for the missing
      fields.

    The default encoding, ``utf-8-sig``, reads UTF-8 and drops a leading
    byte-order mark (as Excel and Windows tools write).

    Objects are read in the order given. The store's ``open_input`` is used
    when it has one, so an object is streamed; otherwise ``get`` reads the
    whole object into memory. ``GcsBlobStore`` has ``open_input``, so GCS
    objects are streamed.

    .. code-block:: python

        store = GcsBlobStore(storage.Client())
        source = BlobLinesSource("gs://bucket/orders/2026-10-09.jsonl", store)
    """

    def __init__(self, uris: Union[str, Sequence[str]], blob_store: Any, *,
                 format: str = "jsonl", encoding: str = "utf-8-sig") -> None:
        if blob_store is None:
            raise ValueError("BlobLinesSource needs a blob_store")
        self._uris = [uris] if isinstance(uris, str) else list(uris)
        if not self._uris or any(not u for u in self._uris):
            raise ValueError("BlobLinesSource needs at least one non-empty uri")
        if format not in _FORMATS:
            raise ValueError(f"BlobLinesSource format must be one of {_FORMATS}, got {format!r}")
        self._store = blob_store
        self._format = format
        self._encoding = encoding

    def read(self, context: Any) -> Iterator[Mapping[str, Any]]:
        for uri in self._uris:
            with self._open(uri) as text:
                if self._format == "csv":
                    yield from _csv_rows(uri, text)
                else:
                    yield from _json_lines(uri, text)

    def _open(self, uri: str) -> io.TextIOBase:
        open_input = getattr(self._store, "open_input", None)
        raw = open_input(uri) if callable(open_input) else io.BytesIO(self._store.get(uri))
        return io.TextIOWrapper(raw, encoding=self._encoding, newline="")


def _csv_rows(uri: str, text: io.TextIOBase) -> Iterator[Mapping[str, Any]]:
    reader = csv.DictReader(text)
    for row in reader:
        if None in row:
            raise ValueError(f"{uri} line {reader.line_num}: {len(row[None])} more field(s) "
                             f"than the header has")
        yield row


def _json_lines(uri: str, text: io.TextIOBase) -> Iterator[Mapping[str, Any]]:
    for number, line in enumerate(text, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{uri} line {number}: not valid JSON: {e.msg}") from None
        if not isinstance(record, dict):
            raise ValueError(f"{uri} line {number}: expected a JSON object, got "
                             f"{type(record).__name__}")
        yield record


__all__ = ["BlobLinesSource"]
