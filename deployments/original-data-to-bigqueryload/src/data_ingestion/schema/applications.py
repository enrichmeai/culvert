"""
Generic Applications Entity Schema.
"""
from gcp_pipeline_core.schema import SchemaField, EntitySchema
from ..config import ALLOWED_APPLICATION_STATUSES

APPLICATIONS_FIELDS = [
    SchemaField(
        name="application_id",
        field_type="STRING",
        required=True,
        is_primary_key=True,
        description="Unique application identifier",
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
        name="loan_amount",
        field_type="FLOAT",
        required=False,
        description="Requested loan amount",
    ),
    SchemaField(
        name="interest_rate",
        field_type="FLOAT",
        required=False,
        description="Interest rate for the loan",
    ),
    SchemaField(
        name="term_months",
        field_type="INTEGER",
        required=False,
        description="Loan term in months",
    ),
    SchemaField(
        name="application_date",
        field_type="DATE",
        required=True,
        description="Date of application submission",
    ),
    SchemaField(
        name="status",
        field_type="STRING",
        required=True,
        allowed_values=ALLOWED_APPLICATION_STATUSES,
        description="Current status of application",
    ),
    SchemaField(
        name="event_type",
        field_type="STRING",
        required=False,
        description="Type of event",
    ),
    SchemaField(
        name="account_type",
        field_type="STRING",
        required=False,
        description="Type of account",
    ),
]

ApplicationsSchema = EntitySchema(
    entity_name="applications",
    system_id="GENERIC",
    fields=APPLICATIONS_FIELDS,
    primary_key=["application_id"],
    description="Generic Application records",
    partition_field="application_date",
    cluster_fields=["_run_id", "status"],
)
