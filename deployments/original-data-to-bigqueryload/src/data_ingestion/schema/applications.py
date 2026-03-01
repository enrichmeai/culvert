"""
Generic Applications Entity Schema (LOA).
"""
from gcp_pipeline_core.schema import SchemaField, EntitySchema
from ..config import ALLOWED_APPLICATION_STATUSES

LOA_APPLICATIONS_FIELDS = [
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
        name="application_type",
        field_type="STRING",
        required=True,
        description="Type of application",
    ),
    SchemaField(
        name="status",
        field_type="STRING",
        required=True,
        allowed_values=ALLOWED_APPLICATION_STATUSES,
        description="Current status of application",
    ),
    SchemaField(
        name="submission_date",
        field_type="TIMESTAMP",
        required=True,
        description="When application was submitted",
    ),
    SchemaField(
        name="amount_requested",
        field_type="FLOAT",
        required=False,
        description="Requested credit amount",
    ),
]

LOAApplicationsSchema = EntitySchema(
    entity_name="applications",
    system_id="LOA",
    fields=LOA_APPLICATIONS_FIELDS,
    primary_key=["application_id"],
    description="LOA Application records",
    partition_field="submission_date",
    cluster_fields=["_run_id", "status"],
)
