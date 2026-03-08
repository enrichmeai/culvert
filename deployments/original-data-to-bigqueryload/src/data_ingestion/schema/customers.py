"""
Generic Customers Entity Schema.
"""

from gcp_pipeline_core.schema import SchemaField, EntitySchema

from ..config import ALLOWED_STATUSES


EM_CUSTOMER_FIELDS = [
    SchemaField(
        name="customer_id",
        field_type="STRING",
        required=True,
        is_primary_key=True,
        description="Unique customer identifier",
    ),
    SchemaField(
        name="first_name",
        field_type="STRING",
        required=True,
        max_length=100,
        description="Customer first name",
    ),
    SchemaField(
        name="last_name",
        field_type="STRING",
        required=True,
        max_length=100,
        description="Customer last name",
    ),
    SchemaField(
        name="ssn",
        field_type="STRING",
        required=True,
        is_pii=True,
        pii_type="SSN",
        description="Social Security Number (PII)",
    ),
    SchemaField(
        name="dob",
        field_type="DATE",
        required=True,
        is_pii=True,
        pii_type="DATE_OF_BIRTH",
        description="Date of birth (PII)",
    ),
    SchemaField(
        name="status",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_STATUSES,
        description="Status: A=Active, I=Inactive, C=Closed",
    ),
    SchemaField(
        name="created_date",
        field_type="DATE",
        required=False,
        description="Customer creation date",
    ),
]

EMCustomerSchema = EntitySchema(
    entity_name="customers",
    system_id="Generic",
    fields=EM_CUSTOMER_FIELDS,
    primary_key=["customer_id"],
    description="Generic Customer records",
    partition_field="created_date",
    cluster_fields=["_run_id", "status"],
)

