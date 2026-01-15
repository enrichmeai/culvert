"""
LOA Applications Entity Schema.

Entity schema definition for LOA Applications.
"""

from gcp_pipeline_core.schema import SchemaField, EntitySchema

from ..config import (
    ALLOWED_APPLICATION_STATUSES,
    ALLOWED_APPLICATION_TYPES,
    ALLOWED_ACCOUNT_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_EVENT_TYPES,
    ALLOWED_TRANSACTION_TYPES,
    ALLOWED_EXCESS_STATUSES,
)


LOA_APPLICATIONS_FIELDS = [
    # Primary identification
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
        description="Customer identifier",
    ),
    # Application details
    SchemaField(
        name="application_date",
        field_type="DATE",
        required=True,
        description="Date application was submitted",
    ),
    SchemaField(
        name="application_type",
        field_type="STRING",
        required=True,
        allowed_values=ALLOWED_APPLICATION_TYPES,
        description="Type: NEW, REFINANCE, MODIFICATION, RENEWAL",
    ),
    SchemaField(
        name="application_status",
        field_type="STRING",
        required=True,
        allowed_values=ALLOWED_APPLICATION_STATUSES,
        description="Status: PENDING, APPROVED, DECLINED, CANCELLED, COMPLETED",
    ),
    # Loan details
    SchemaField(
        name="loan_amount",
        field_type="NUMERIC",
        required=True,
        description="Requested loan amount",
    ),
    SchemaField(
        name="loan_term",
        field_type="INTEGER",
        required=False,
        description="Loan term in months",
    ),
    SchemaField(
        name="interest_rate",
        field_type="NUMERIC",
        required=False,
        description="Interest rate as percentage",
    ),
    # Portfolio attributes
    SchemaField(
        name="portfolio_id",
        field_type="STRING",
        required=False,
        description="Portfolio identifier",
    ),
    SchemaField(
        name="portfolio_name",
        field_type="STRING",
        required=False,
        description="Portfolio name",
    ),
    SchemaField(
        name="portfolio_type",
        field_type="STRING",
        required=False,
        description="Portfolio type",
    ),
    # Account attributes
    SchemaField(
        name="account_id",
        field_type="STRING",
        required=False,
        description="Account identifier",
    ),
    SchemaField(
        name="account_number",
        field_type="STRING",
        required=False,
        description="Account number",
    ),
    SchemaField(
        name="account_type",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_ACCOUNT_TYPES,
        description="Account type: CHECKING, SAVINGS, LOAN, CREDIT",
    ),
    SchemaField(
        name="account_status",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_ACCOUNT_STATUSES,
        description="Account status: ACTIVE, INACTIVE, CLOSED, SUSPENDED",
    ),
    # Event attributes
    SchemaField(
        name="event_type",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_EVENT_TYPES,
        description="Event type: SUBMITTED, REVIEWED, APPROVED, FUNDED, CLOSED",
    ),
    SchemaField(
        name="event_date",
        field_type="DATE",
        required=False,
        description="Event date",
    ),
    SchemaField(
        name="event_status",
        field_type="STRING",
        required=False,
        description="Event status",
    ),
    # Transaction attributes
    SchemaField(
        name="transaction_id",
        field_type="STRING",
        required=False,
        description="Transaction identifier",
    ),
    SchemaField(
        name="transaction_amount",
        field_type="NUMERIC",
        required=False,
        description="Transaction amount",
    ),
    SchemaField(
        name="transaction_date",
        field_type="DATE",
        required=False,
        description="Transaction date",
    ),
    SchemaField(
        name="transaction_type",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_TRANSACTION_TYPES,
        description="Transaction type: DISBURSEMENT, PAYMENT, FEE, ADJUSTMENT, REVERSAL",
    ),
    # Excess attributes
    SchemaField(
        name="excess_amount",
        field_type="NUMERIC",
        required=False,
        description="Excess amount",
    ),
    SchemaField(
        name="excess_reason",
        field_type="STRING",
        required=False,
        description="Reason for excess",
    ),
    SchemaField(
        name="excess_status",
        field_type="STRING",
        required=False,
        allowed_values=ALLOWED_EXCESS_STATUSES,
        description="Excess status: IDENTIFIED, REVIEWED, RESOLVED, WAIVED",
    ),
    SchemaField(
        name="excess_category",
        field_type="STRING",
        required=False,
        description="Excess category",
    ),
    SchemaField(
        name="excess_threshold",
        field_type="NUMERIC",
        required=False,
        description="Excess threshold amount",
    ),
]

LOAApplicationsSchema = EntitySchema(
    entity_name="applications",
    system_id="LOA",
    fields=LOA_APPLICATIONS_FIELDS,
    primary_key=["application_id"],
    description="LOA loan application records containing application, account, event, transaction, and excess information",
    partition_field="_extract_date",
    cluster_fields=["application_status", "application_type"],
)

