"""
Application1 Constants.

Field headers and allowed values for Application1 entities.
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

# Allowed values
ALLOWED_STATUSES = ["A", "I", "C"]
ALLOWED_ACCOUNT_TYPES = ["CHECKING", "SAVINGS", "MONEY_MARKET", "CD", "IRA"]
ALLOWED_DECISION_CODES = ["APPROVE", "DECLINE", "REVIEW", "PENDING"]

# Score range
SCORE_MIN = 300
SCORE_MAX = 850

