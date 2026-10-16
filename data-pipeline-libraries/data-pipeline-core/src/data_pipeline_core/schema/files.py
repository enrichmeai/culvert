"""Entity schema files: one entity's layout as YAML (JSON is accepted too).

A product supplies its layout as configuration rather than as code::

    entity: customers                # required
    version: "1"                     # optional, default "1"
    description: Customer records    # optional
    headers: [customer_id, ssn, dob] # required: the file's columns, in order
    fields:                          # required: one entry per field
      - name: customer_id            #   required
        type: STRING                 #   required, see TYPES
        required: true               #   optional, default false
        description: ...             #   optional
        classification: restricted   #   optional: public | internal | confidential | restricted
        masking: hash                #   optional: a strategy, or {strategy, replacement, salt}
        range: {min: 0, max: 150}    #   optional: closed numeric bounds
        allowed: [A, I, C]           #   optional, STRING fields only: the values it may hold
    primary_key: [customer_id]       # optional: field names
    partition_key: dob               # optional: a field name
    envelope:                        # optional HDR/TRL overrides
      system_id: Generic
      csv_header_row: true

The file is refused, with a :class:`SchemaFileError` naming the file and the
entry, when it is not a mapping, has a key this format does not define (a
misspelt ``requried`` is an error, not a field that silently stays optional),
lacks a required entry, names an unknown type, repeats a field, a header or a
key, has a header that names no field or a field no header supplies, or has an
invalid classification, masking strategy, range or list of allowed values.

Mirrors the Java ``com.enrichmeai.culvert.schema.EntitySchemas``: the same
format, rules and messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse
from urllib.request import url2pathname

import yaml

from data_pipeline_core.dataquality.numeric_range import NumericRange
from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import MaskingPolicy, MaskingStrategy
from data_pipeline_core.schema.entity import EntitySchema, SchemaField

#: The field types a schema file may use: the warehouse-neutral wire types Culvert maps.
TYPES = frozenset(
    {
        "STRING",
        "INT64",
        "FLOAT64",
        "BOOL",
        "NUMERIC",
        "BIGNUMERIC",
        "DATE",
        "DATETIME",
        "TIMESTAMP",
        "BYTES",
        "JSON",
    }
)

_TOP_KEYS = {
    "entity",
    "version",
    "description",
    "headers",
    "fields",
    "primary_key",
    "partition_key",
    "envelope",
}
_FIELD_KEYS = {
    "name", "type", "required", "description", "classification", "masking", "range", "allowed"
}
_MASKING_KEYS = {"strategy", "replacement", "salt"}
_RANGE_KEYS = {"min", "max"}
_ENVELOPE_KEYS = {"system_id", "csv_header_row"}


class SchemaFileError(ValueError):
    """An entity schema file that cannot be read or does not describe a valid layout.

    The message names the file and the offending entry, e.g.
    ``customers.schema.yaml: fields[3].type: unknown type 'STRNG'``.
    """


@dataclass(frozen=True)
class EnvelopeSettings:
    """The HDR/TRL envelope settings a schema file may override.

    Each is ``None`` when the file does not set it, and the loader that reads
    the envelope applies its own default.
    """

    system_id: Optional[str] = None
    csv_header_row: Optional[bool] = None


@dataclass(frozen=True)
class EntitySchemaFile:
    """One entity's layout, as an entity schema file describes it.

    ``schema`` is the entity schema (its name is the file's ``entity``),
    ``headers`` the file's columns in order (each names a field), and
    ``envelope`` any envelope overrides. Mirrors the Java ``EntitySchemaFile``.
    """

    schema: EntitySchema
    headers: List[str]
    envelope: EnvelopeSettings = field(default_factory=EnvelopeSettings)


def load_entity_schema(uri_or_path: Union[str, Path], store: Any = None) -> EntitySchemaFile:
    """Load a schema file from a local path, a ``file:`` URI, or any URI ``store`` reads.

    ``store`` is a ``BlobStore`` for remote URIs (``gs://``, ``s3://``, ...);
    it may be ``None`` when the location is local.
    """
    return parse_entity_schema(read_entity_schema(uri_or_path, store), str(uri_or_path))


def read_entity_schema(uri_or_path: Union[str, Path], store: Any = None) -> str:
    """The text of a schema file, read as :func:`load_entity_schema` reads it."""
    location = str(uri_or_path)
    if not location.strip():
        raise SchemaFileError("schema file location must not be blank")
    if location.startswith("file:"):
        return _read_local(Path(url2pathname(urlparse(location).path)), location)
    if "://" not in location:
        return _read_local(Path(location), location)
    if store is None:
        raise SchemaFileError(f"{location}: no store to read a remote schema file from")
    try:
        return store.get(location).decode("utf-8")
    except Exception as exc:  # whatever the store raises, the message names the file
        raise SchemaFileError(f"{location}: cannot read the schema file: {exc}") from exc


def parse_entity_schema(text: str, source: str) -> EntitySchemaFile:
    """Parse and validate the text of a schema file; ``source`` names it in messages."""
    try:
        root = yaml.load(text, Loader=_NoDuplicateKeysLoader)  # noqa: S506 - a SafeLoader subclass
    except yaml.YAMLError as exc:
        raise SchemaFileError(f"{source}: not valid YAML or JSON: {exc}") from exc
    return _Reader(source).file(root)


def _read_local(path: Path, source: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SchemaFileError(f"{source}: cannot read the schema file: {exc}") from exc


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    """PyYAML's safe loader keeps the last of two equal keys; this one refuses them."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError:
                raise yaml.constructor.ConstructorError(
                    None, None, f"found a key that is not a scalar: {key!r}", key_node.start_mark
                ) from None
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"found duplicate key {key!r}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


class _Reader:
    """Walks the parsed document, naming each entry it rejects by its path in the file."""

    def __init__(self, source: str) -> None:
        self.source = source

    def file(self, root: Any) -> EntitySchemaFile:
        top = self._mapping(root, "the file")
        self._only_keys(top, _TOP_KEYS, "the file")

        entity = self._required_string(top, "entity", "entity")
        version = self._scalar_string(top["version"], "version") if "version" in top else "1"
        description = self._optional_string(top, "description", "description")

        headers = self._string_list(self._require(top, "headers", "headers"), "headers")
        if not headers:
            raise self._error("headers", "must list at least one header")
        fields = self._fields(self._require(top, "fields", "fields"))

        field_names = {f.name for f in fields}
        seen_headers: set = set()
        for i, header in enumerate(headers):
            if header in seen_headers:
                raise self._error(f"headers[{i}]", f"duplicate header '{header}'")
            seen_headers.add(header)
            if header not in field_names:
                raise self._error(f"headers[{i}]", f"header '{header}' names no field")
        for i, f in enumerate(fields):
            if f.name not in seen_headers:
                raise self._error(f"fields[{i}]", f"field '{f.name}' has no header")

        primary_key = (
            self._string_list(top["primary_key"], "primary_key") if "primary_key" in top else []
        )
        for i, key in enumerate(primary_key):
            if key not in field_names:
                raise self._error(f"primary_key[{i}]", f"'{key}' names no field")
        partition_key = self._optional_string(top, "partition_key", "partition_key")
        if partition_key is not None and partition_key not in field_names:
            raise self._error("partition_key", f"'{partition_key}' names no field")

        schema = EntitySchema(
            name=entity,
            fields=fields,
            version=version,
            description=description,
            primary_key=primary_key,
            partition_key=partition_key,
        )
        return EntitySchemaFile(
            schema=schema, headers=headers, envelope=self._envelope(top.get("envelope"))
        )

    def _fields(self, value: Any) -> List[SchemaField]:
        if not isinstance(value, list) or not value:
            raise self._error("fields", "must be a non-empty list of fields")
        fields: List[SchemaField] = []
        names: set = set()
        for i, item in enumerate(value):
            at = f"fields[{i}]"
            entry = self._mapping(item, at)
            self._only_keys(entry, _FIELD_KEYS, at)
            name = self._required_string(entry, "name", f"{at}.name")
            if name in names:
                raise self._error(f"{at}.name", f"duplicate field '{name}'")
            names.add(name)
            type_ = self._required_string(entry, "type", f"{at}.type").upper()
            if type_ not in TYPES:
                raise self._error(
                    f"{at}.type",
                    f"unknown type '{entry['type']}' (expected one of "
                    f"{', '.join(sorted(TYPES))})",
                )
            required = False
            if "required" in entry:
                if not isinstance(entry["required"], bool):
                    raise self._error(f"{at}.required", "must be true or false")
                required = entry["required"]
            fields.append(
                SchemaField(
                    name=name,
                    type=type_,
                    mode="REQUIRED" if required else "NULLABLE",
                    description=self._optional_string(entry, "description", f"{at}.description"),
                    classification=self._classification(
                        entry.get("classification"), f"{at}.classification"
                    ),
                    masking=self._masking(entry.get("masking"), f"{at}.masking"),
                    range=self._range(entry.get("range"), f"{at}.range"),
                    allowed=self._allowed(entry.get("allowed"), name, type_, f"{at}.allowed"),
                )
            )
        return fields

    def _classification(self, value: Any, at: str) -> Optional[DataClassification]:
        if value is None:
            return None
        text = self._scalar_string(value, at)
        for c in DataClassification:
            if c.value.lower() == text.lower() or c.name.lower() == text.lower():
                return c
        raise self._error(
            at,
            f"unknown classification '{text}' (expected public, internal, confidential"
            f" or restricted)",
        )

    def _masking(self, value: Any, at: str) -> Optional[MaskingPolicy]:
        if value is None:
            return None
        if isinstance(value, dict):
            entry = self._mapping(value, at)
            self._only_keys(entry, _MASKING_KEYS, at)
            strategy = self._strategy(
                self._required_string(entry, "strategy", f"{at}.strategy"), f"{at}.strategy"
            )
            replacement = self._optional_string(entry, "replacement", f"{at}.replacement")
            salt = self._optional_string(entry, "salt", f"{at}.salt")
            return MaskingPolicy(
                strategy=strategy,
                replacement="*" if replacement is None else replacement,
                salt="" if salt is None else salt,
            )
        return MaskingPolicy(strategy=self._strategy(self._scalar_string(value, at), at))

    def _strategy(self, text: str, at: str) -> MaskingStrategy:
        for s in MaskingStrategy:
            if s.name.lower() == text.lower():
                return s
        raise self._error(
            at,
            f"unknown masking strategy '{text}' (expected full, partial, redacted, hash"
            f" or none)",
        )

    def _range(self, value: Any, at: str) -> Optional[NumericRange]:
        if value is None:
            return None
        entry = self._mapping(value, at)
        self._only_keys(entry, _RANGE_KEYS, at)
        lo = self._number(self._require(entry, "min", f"{at}.min"), f"{at}.min")
        hi = self._number(self._require(entry, "max", f"{at}.max"), f"{at}.max")
        if hi < lo:
            raise self._error(at, f"max ({hi}) must be >= min ({lo})")
        return NumericRange.of(lo, hi)

    def _allowed(self, value: Any, name: str, type_: str, at: str) -> Optional[Tuple[str, ...]]:
        if value is None:
            return None
        if type_ != "STRING":
            raise self._error(at, f"allowed values are for STRING fields, and '{name}' is {type_}")
        if not isinstance(value, list) or not value:
            raise self._error(at, "must be a non-empty list of values")
        values = self._string_list(value, at)
        for i, text in enumerate(values):
            if text in values[:i]:
                raise self._error(f"{at}[{i}]", f"duplicate value '{text}'")
        return tuple(values)

    def _envelope(self, value: Any) -> EnvelopeSettings:
        if value is None:
            return EnvelopeSettings()
        entry = self._mapping(value, "envelope")
        self._only_keys(entry, _ENVELOPE_KEYS, "envelope")
        csv_header_row = None
        if "csv_header_row" in entry:
            if not isinstance(entry["csv_header_row"], bool):
                raise self._error("envelope.csv_header_row", "must be true or false")
            csv_header_row = entry["csv_header_row"]
        return EnvelopeSettings(
            system_id=self._optional_string(entry, "system_id", "envelope.system_id"),
            csv_header_row=csv_header_row,
        )

    # ------------------------------------------------------------------ shapes

    def _mapping(self, value: Any, at: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise self._error(at, "must be a mapping")
        for key in value:
            if not isinstance(key, str):
                raise self._error(at, f"has a key that is not a string: {key}")
        return value

    def _only_keys(self, mapping: Dict[str, Any], allowed: set, at: str) -> None:
        for key in mapping:
            if key not in allowed:
                raise self._error(
                    at, f"unknown key '{key}' (expected {', '.join(sorted(allowed))})"
                )

    def _require(self, mapping: Dict[str, Any], key: str, at: str) -> Any:
        value = mapping.get(key)
        if value is None:
            raise self._error(at, "is required")
        return value

    def _required_string(self, mapping: Dict[str, Any], key: str, at: str) -> str:
        text = self._scalar_string(self._require(mapping, key, at), at)
        if not text.strip():
            raise self._error(at, "must not be blank")
        return text

    def _optional_string(self, mapping: Dict[str, Any], key: str, at: str) -> Optional[str]:
        return None if mapping.get(key) is None else self._scalar_string(mapping[key], at)

    def _scalar_string(self, value: Any, at: str) -> str:
        """A string; an integer is accepted and written as YAML wrote it (version: 1 is "1")."""
        if isinstance(value, str):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        raise self._error(
            at, "must be a string (quote it if YAML reads it as another type, e.g. 1.0)"
        )

    def _string_list(self, value: Any, at: str) -> List[str]:
        if not isinstance(value, list):
            raise self._error(at, "must be a list")
        out: List[str] = []
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise self._error(
                    f"{at}[{i}]",
                    "must be a non-blank string (quote it if YAML reads it as"
                    " another type, e.g. 'on' or 'no')",
                )
            out.append(item)
        return out

    def _number(self, value: Any, at: str) -> float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        raise self._error(at, "must be a number")

    def _error(self, at: str, message: str) -> SchemaFileError:
        return SchemaFileError(f"{self.source}: {at}: {message}")
