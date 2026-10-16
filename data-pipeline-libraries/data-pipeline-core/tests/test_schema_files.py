"""Entity schema files: the format, and every way a file is refused.

The Java ``EntitySchemasTest`` runs the same cases and expects the same
messages; the four sample files are the ones the ODP loader ships
(``deployments/original-data-to-bigqueryload-java/schemas``), and Java's
``GenericEntitiesSchemaFileParityTest`` holds them equal to its built-in layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from data_pipeline_core.dataquality.numeric_range import NumericRange
from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import MaskingPolicy, MaskingStrategy
from data_pipeline_core.schema import (
    EntitySchema,
    EntitySchemaFile,
    EnvelopeSettings,
    SchemaField,
    SchemaFileError,
    load_entity_schema,
    parse_entity_schema,
)

SAMPLES = (
    Path(__file__).resolve().parents[3]
    / "deployments"
    / "original-data-to-bigqueryload-java"
    / "schemas"
)

FULL = """
entity: customers
version: 2
description: Customer records
headers: [customer_id, ssn, age, score]
fields:
  - name: customer_id
    type: string
    required: true
  - name: ssn
    type: STRING
    required: true
    description: Social security number
    classification: restricted
    masking: {strategy: partial, replacement: "#"}
  - name: age
    type: INT64
    range: {min: 0, max: 150}
  - name: score
    type: FLOAT64
    classification: INTERNAL
    masking: hash
primary_key: [customer_id]
partition_key: age
envelope:
  system_id: Retail
  csv_header_row: false
"""


def test_reads_every_part_of_the_format():
    file = parse_entity_schema(FULL, "customers.schema.yaml")

    assert file.headers == ["customer_id", "ssn", "age", "score"]
    assert file.envelope == EnvelopeSettings(system_id="Retail", csv_header_row=False)
    assert file.schema == EntitySchema(
        name="customers",
        fields=[
            SchemaField("customer_id", "STRING", "REQUIRED"),
            SchemaField(
                "ssn",
                "STRING",
                "REQUIRED",
                description="Social security number",
                classification=DataClassification.RESTRICTED,
                masking=MaskingPolicy(MaskingStrategy.PARTIAL, replacement="#"),
            ),
            SchemaField("age", "INT64", range=NumericRange.of(0, 150)),
            SchemaField(
                "score",
                "FLOAT64",
                classification=DataClassification.INTERNAL,
                masking=MaskingPolicy(MaskingStrategy.HASH),
            ),
        ],
        version="2",
        description="Customer records",
        primary_key=["customer_id"],
        partition_key="age",
    )


def test_reads_json_too():
    text = """{"entity": "accounts", "headers": ["account_id", "balance"],
               "fields": [{"name": "account_id", "type": "STRING", "required": true},
                          {"name": "balance", "type": "NUMERIC"}]}"""

    file = parse_entity_schema(text, "accounts.schema.json")

    assert file.schema == EntitySchema(
        "accounts",
        [SchemaField("account_id", "STRING", "REQUIRED"), SchemaField("balance", "NUMERIC")],
    )
    assert file.envelope == EnvelopeSettings()


def test_loads_a_local_path_and_a_file_uri(tmp_path):
    path = tmp_path / "accounts.schema.yaml"
    path.write_text("entity: accounts\nheaders: [id]\nfields: [{name: id, type: STRING}]\n")

    assert load_entity_schema(path).schema.name == "accounts"
    assert load_entity_schema(str(path)).headers == ["id"]
    assert load_entity_schema(path.as_uri()).headers == ["id"]


class _OneObjectStore:
    def __init__(self, uri: str, text: str) -> None:
        self.uri, self.text = uri, text

    def get(self, uri: str) -> bytes:
        if uri != self.uri:
            raise FileNotFoundError(uri)
        return self.text.encode()


def test_loads_a_remote_uri_through_the_store():
    store = _OneObjectStore(
        "gs://schemas/accounts.schema.yaml",
        "entity: accounts\nheaders: [id]\nfields: [{name: id, type: STRING}]\n",
    )

    assert load_entity_schema("gs://schemas/accounts.schema.yaml", store).schema.name == "accounts"
    with pytest.raises(
        SchemaFileError, match="^gs://schemas/missing.schema.yaml: cannot read the schema file"
    ):
        load_entity_schema("gs://schemas/missing.schema.yaml", store)
    with pytest.raises(SchemaFileError, match="no store to read a remote schema file from"):
        load_entity_schema("gs://schemas/accounts.schema.yaml")


# Each invalid file and the start of its message, after "s.yaml: ". The same table as Java's.
INVALID = [
    (
        "unknown type",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRNG}]",
        "fields[0].type: unknown type 'STRNG'",
    ),
    (
        "duplicate field",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING}, {name: a, type: INT64}]",
        "fields[1].name: duplicate field 'a'",
    ),
    (
        "header naming no field",
        "entity: e\nheaders: [a, b]\nfields: [{name: a, type: STRING}]",
        "headers[1]: header 'b' names no field",
    ),
    (
        "field with no header",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING}, {name: b, type: STRING}]",
        "fields[1]: field 'b' has no header",
    ),
    (
        "duplicate header",
        "entity: e\nheaders: [a, a]\nfields: [{name: a, type: STRING}]",
        "headers[1]: duplicate header 'a'",
    ),
    ("missing entity", "headers: [a]\nfields: [{name: a, type: STRING}]", "entity: is required"),
    (
        "blank entity",
        "entity: ' '\nheaders: [a]\nfields: [{name: a, type: STRING}]",
        "entity: must not be blank",
    ),
    ("missing headers", "entity: e\nfields: [{name: a, type: STRING}]", "headers: is required"),
    (
        "empty headers",
        "entity: e\nheaders: []\nfields: [{name: a, type: STRING}]",
        "headers: must list at least one header",
    ),
    ("missing fields", "entity: e\nheaders: [a]", "fields: is required"),
    (
        "empty fields",
        "entity: e\nheaders: [a]\nfields: []",
        "fields: must be a non-empty list of fields",
    ),
    (
        "missing field name",
        "entity: e\nheaders: [a]\nfields: [{type: STRING}]",
        "fields[0].name: is required",
    ),
    (
        "missing field type",
        "entity: e\nheaders: [a]\nfields: [{name: a}]",
        "fields[0].type: is required",
    ),
    (
        "misspelt key",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, requried: true}]",
        "fields[0]: unknown key 'requried'",
    ),
    (
        "unknown top-level key",
        "entity: e\nheader: [a]\nfields: [{name: a, type: STRING}]",
        "the file: unknown key 'header'",
    ),
    (
        "required not a boolean",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, required: maybe}]",
        "fields[0].required: must be true or false",
    ),
    (
        "unknown classification",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, classification: secret}]",
        "fields[0].classification: unknown classification 'secret'",
    ),
    (
        "unknown masking strategy",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, masking: shred}]",
        "fields[0].masking: unknown masking strategy 'shred'",
    ),
    (
        "masking without a strategy",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, masking: {salt: x}}]",
        "fields[0].masking.strategy: is required",
    ),
    (
        "range missing max",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: INT64, range: {min: 1}}]",
        "fields[0].range.max: is required",
    ),
    (
        "range upside down",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: INT64, range: {min: 5, max: 1}}]",
        "fields[0].range: max (1.0) must be >= min (5.0)",
    ),
    (
        "primary key naming no field",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING}]\nprimary_key: [b]",
        "primary_key[0]: 'b' names no field",
    ),
    (
        "header YAML reads as a bool",
        "entity: e\nheaders: [on]\nfields: [{name: a, type: STRING}]",
        "headers[0]: must be a non-blank string",
    ),
    (
        "allowed on a non-STRING field",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: INT64, allowed: [1, 2]}]",
        "fields[0].allowed: allowed values are for STRING fields, and 'a' is INT64",
    ),
    (
        "allowed empty",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, allowed: []}]",
        "fields[0].allowed: must be a non-empty list of values",
    ),
    (
        "allowed not a list",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, allowed: A}]",
        "fields[0].allowed: must be a non-empty list of values",
    ),
    (
        "allowed value YAML reads as a number",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, allowed: [A, 01]}]",
        "fields[0].allowed[1]: must be a non-blank string",
    ),
    (
        "duplicate allowed value",
        "entity: e\nheaders: [a]\nfields: [{name: a, type: STRING, allowed: [A, I, A]}]",
        "fields[0].allowed[2]: duplicate value 'A'",
    ),
    ("not a mapping", "- just a list", "the file: must be a mapping"),
]


def test_reads_allowed_values():
    file = parse_entity_schema(
        "entity: accounts\nheaders: [status]\n"
        "fields: [{name: status, type: STRING, allowed: [A, I, C]}]",
        "accounts.schema.yaml",
    )

    assert file.schema.fields == [SchemaField("status", "STRING", allowed=("A", "I", "C"))]


@pytest.mark.parametrize("name, text, message", INVALID, ids=[case[0] for case in INVALID])
def test_refuses(name, text, message):
    with pytest.raises(SchemaFileError) as raised:
        parse_entity_schema(text, "s.yaml")
    assert str(raised.value).startswith("s.yaml: " + message)


def test_refuses_text_that_is_not_yaml():
    with pytest.raises(SchemaFileError, match="^s.yaml: not valid YAML or JSON"):
        parse_entity_schema("entity: [unclosed", "s.yaml")


def test_refuses_a_duplicate_key():
    with pytest.raises(SchemaFileError, match="^s.yaml: not valid YAML or JSON"):
        parse_entity_schema(
            "entity: a\nentity: b\nheaders: [x]\nfields: [{name: x, type: STRING}]\n", "s.yaml"
        )


def _req(name, type_):
    return SchemaField(name, type_, "REQUIRED")


def _opt(name, type_):
    return SchemaField(name, type_, "NULLABLE")


# The ODP loader's built-in layouts (GenericEntities.java), field by field.
SAMPLE_LAYOUTS = {
    "customers": [
        _req("customer_id", "STRING"),
        _req("first_name", "STRING"),
        _req("last_name", "STRING"),
        _req("ssn", "STRING"),
        _req("dob", "DATE"),
        _opt("status", "STRING"),
        _opt("created_date", "DATE"),
    ],
    "accounts": [
        _req("account_id", "STRING"),
        _req("customer_id", "STRING"),
        _opt("account_type", "STRING"),
        _opt("balance", "NUMERIC"),
        _opt("status", "STRING"),
        _opt("open_date", "DATE"),
    ],
    "decision": [
        _req("decision_id", "STRING"),
        _req("customer_id", "STRING"),
        _opt("application_id", "STRING"),
        _req("decision_code", "STRING"),
        _req("decision_date", "TIMESTAMP"),
        _opt("score", "INT64"),
        _opt("reason_codes", "STRING"),
    ],
    "applications": [
        _req("application_id", "STRING"),
        _req("customer_id", "STRING"),
        _opt("loan_amount", "FLOAT64"),
        _opt("interest_rate", "FLOAT64"),
        _opt("term_months", "INT64"),
        _req("application_date", "DATE"),
        _req("status", "STRING"),
        _opt("event_type", "STRING"),
        _opt("account_type", "STRING"),
    ],
}


@pytest.mark.parametrize("entity", sorted(SAMPLE_LAYOUTS))
def test_the_loaders_sample_files_read_the_same_in_python(entity):
    fields = SAMPLE_LAYOUTS[entity]

    assert load_entity_schema(SAMPLES / f"{entity}.schema.yaml") == EntitySchemaFile(
        schema=EntitySchema(entity, fields),
        headers=[f.name for f in fields],
        envelope=EnvelopeSettings(),
    )


def test_refuses_a_complex_key():
    with pytest.raises(SchemaFileError, match="^s.yaml: "):
        parse_entity_schema("? [a]\n: x\n", "s.yaml")


def test_refuses_a_file_that_is_not_utf8(tmp_path):
    path = tmp_path / "bad.schema.yaml"
    path.write_bytes(b"entity: \xff")

    with pytest.raises(SchemaFileError) as raised:
        load_entity_schema(str(path))
    assert str(raised.value).startswith(f"{path}: cannot read the schema file")


def test_refuses_a_remote_file_that_is_not_utf8():
    store = _OneObjectStore("gs://s/bad.schema.yaml", "")
    store.text = None
    store.get = lambda uri: b"e: \xff"

    with pytest.raises(
        SchemaFileError, match="^gs://s/bad.schema.yaml: cannot read the schema file"
    ):
        load_entity_schema("gs://s/bad.schema.yaml", store)
