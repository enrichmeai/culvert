"""
Application2 Constants.

Field headers and allowed values for Application2 Applications entity.
"""

# CSV Headers for Applications entity
APPLICATIONS_HEADERS = [
    "application_id",
    "customer_id",
    "application_date",
    "application_type",
    "application_status",
    "loan_amount",
    "loan_term",
    "interest_rate",
    "portfolio_id",
    "portfolio_name",
    "portfolio_type",
    "account_id",
    "account_number",
    "account_type",
    "account_status",
    "event_type",
    "event_date",
    "event_status",
    "transaction_id",
    "transaction_amount",
    "transaction_date",
    "transaction_type",
    "excess_amount",
    "excess_reason",
    "excess_status",
    "excess_category",
    "excess_threshold",
]

# Allowed values for application_status
ALLOWED_APPLICATION_STATUSES = [
    "PENDING",
    "APPROVED",
    "DECLINED",
    "CANCELLED",
    "COMPLETED",
]

# Allowed values for application_type
ALLOWED_APPLICATION_TYPES = [
    "NEW",
    "REFINANCE",
    "MODIFICATION",
    "RENEWAL",
]

# Allowed values for account_status
ALLOWED_ACCOUNT_STATUSES = [
    "ACTIVE",
    "INACTIVE",
    "CLOSED",
    "SUSPENDED",
]

# Allowed values for account_type
ALLOWED_ACCOUNT_TYPES = [
    "CHECKING",
    "SAVINGS",
    "LOAN",
    "CREDIT",
]

# Allowed values for event_type
ALLOWED_EVENT_TYPES = [
    "SUBMITTED",
    "REVIEWED",
    "APPROVED",
    "FUNDED",
    "CLOSED",
]

# Allowed values for transaction_type
ALLOWED_TRANSACTION_TYPES = [
    "DISBURSEMENT",
    "PAYMENT",
    "FEE",
    "ADJUSTMENT",
    "REVERSAL",
]

# Allowed values for excess_status
ALLOWED_EXCESS_STATUSES = [
    "IDENTIFIED",
    "REVIEWED",
    "RESOLVED",
    "WAIVED",
]

# Loan amount range (in dollars)
LOAN_AMOUNT_MIN = 1000
LOAN_AMOUNT_MAX = 10000000

# Interest rate range (as percentage)
INTEREST_RATE_MIN = 0.0
INTEREST_RATE_MAX = 30.0

# Loan term range (in months)
LOAN_TERM_MIN = 1
LOAN_TERM_MAX = 480  # 40 years

