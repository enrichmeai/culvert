"""
Generic Decision Entity Schema.
"""

from gcp_pipeline_core.schema import SchemaField, EntitySchema

from ..config import ALLOWED_DECISION_CODES


EM_DECISION_FIELDS = [
    SchemaField(
        name="decision_id",
        field_type="STRING",
        required=True,
        is_primary_key=True,
        description="Unique decision identifier",
    ),
    SchemaField(
        name="customer_id",
        field_type="STRING",
        required=True,
        is_foreign_key=True,
        foreign_key_ref="customers.customer_id",
        description="Foreign key to customers",
    ),
    SchemaField(
        name="application_id",
        field_type="STRING",
        required=False,
        description="Related application ID",
    ),
    SchemaField(
        name="decision_code",
        field_type="STRING",
        required=True,
        allowed_values=ALLOWED_DECISION_CODES,
        description="Decision outcome code",
    ),
    SchemaField(
        name="decision_date",
        field_type="TIMESTAMP",
        required=True,
        description="When decision was made",
    ),
    SchemaField(
        name="score",
        field_type="INTEGER",
        required=False,
        description="Credit score (300-850)",
    ),
    SchemaField(
        name="reason_codes",
        field_type="STRING",
        required=False,
        description="Pipe-separated reason codes",
    ),
]

EMDecisionSchema = EntitySchema(
    entity_name="decision",
    system_id="Generic",
    fields=EM_DECISION_FIELDS,
    primary_key=["decision_id"],
    description="Generic Decision records",
    partition_field="decision_date",
    cluster_fields=["_run_id", "decision_code"],
)

