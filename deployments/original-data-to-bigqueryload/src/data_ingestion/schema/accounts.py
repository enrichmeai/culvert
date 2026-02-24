"""
Generic Accounts Entity Schema.
"""

from gcp_pipeline_core.schema import SchemaField, EntitySchema

from ..config import ALLOWED_STATUSES, ALLOWED_ACCOUNT_TYPES


EM_ACCOUNT_FIELDS = [
    SchemaField(
        name="account_id",
        field_type="STRING",
        required=True,
        is_primary_key=True,
        description="Unique account identifier",
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
        name="account_type",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_ACCOUNT_TYPES,
        description="Account type",
    ),
    SchemaField(
        name="balance",
        field_type="NUMERIC",
        required=False,
        description="Current account balance",
    ),
    SchemaField(
        name="status",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_STATUSES,
        description="Status: A=Active, I=Inactive, C=Closed",
    ),
    SchemaField(
        name="open_date",
        field_type="DATE",
        required=False,
        description="Account open date",
    ),
]

EMAccountSchema = EntitySchema(
    entity_name="accounts",
    system_id="Generic",
    fields=EM_ACCOUNT_FIELDS,
    primary_key=["account_id"],
    description="Generic Account records",
    partition_field="open_date",
    cluster_fields=["_run_id", "account_type"],
)

