"""
Validation error types and structures.
"""

from dataclasses import dataclass


@dataclass
class ValidationError:
    """Structured validation error with PII masking."""
    field: str
    value: str
    message: str
    error_type: str = "VALIDATION_ERROR"

    def __str__(self):
        # Mask PII in error messages
        masked_value = self.value
        if self.field == "ssn" and len(self.value) > 5:
            masked_value = f"***-**-{self.value[-4:]}"
        elif self.field in ["credit_card", "bank_account"] and len(self.value) > 4:
            masked_value = f"****{self.value[-4:]}"
        return f"{self.field}: {self.message} (value: {masked_value})"

