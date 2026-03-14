"""
Generic Constants.

Field headers and allowed values for Generic entities.
"""

# CSV Headers per entity
CUSTOMERS_HEADERS = [
    "customer_id",
    "first_name",
    "last_name",
    "ssn",
    "dob",
    "status",
    "created_date",
]

ACCOUNTS_HEADERS = [
    "account_id",
    "customer_id",
    "account_type",
    "balance",
    "status",
    "open_date",
]

DECISION_HEADERS = [
    "decision_id",
    "customer_id",
    "application_id",
    "decision_code",
    "decision_date",
    "score",
    "reason_codes",
]

APPLICATIONS_HEADERS = [
    "application_id",
    "customer_id",
    "loan_amount",
    "interest_rate",
    "term_months",
    "application_date",
    "status",
    "event_type",
    "account_type",
]

# Allowed values
ALLOWED_STATUSES = ["A", "I", "C"]
ALLOWED_ACCOUNT_TYPES = ["CHECKING", "SAVINGS", "MONEY_MARKET", "CD", "IRA"]
ALLOWED_DECISION_CODES = ["APPROVE", "DECLINE", "REVIEW", "PENDING"]
ALLOWED_APPLICATION_STATUSES = ["SUBMITTED", "IN_PROGRESS", "APPROVED", "DECLINED", "CANCELLED"]

# Score range
SCORE_MIN = 300
SCORE_MAX = 850

