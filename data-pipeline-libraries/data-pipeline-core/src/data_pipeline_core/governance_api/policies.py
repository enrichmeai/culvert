"""Masking and retention policy dataclasses.

The GovernancePolicy Protocol returns these. A concrete
implementation (Dataplex, a static YAML file, Glue Data Catalog) maps
field/table identifiers to the appropriate policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MaskingStrategy(str, Enum):
    """How a field is masked when masking is applied.

    The four values are the masking modes every adapter's PII
    transform implements; the value strings are part of the contract.
    """

    FULL = "full"  # entire value replaced with constant
    PARTIAL = "partial"  # most chars replaced, last 4 kept (last4)
    REDACTED = "redacted"  # value removed, sentinel returned
    HASH = "hash"  # deterministic hash
    NONE = "none"  # explicitly no masking (overrides defaults)


@dataclass(frozen=True)
class MaskingPolicy:
    """Policy: this field is masked using this strategy.

    `replacement` is used by `FULL`/`REDACTED` (e.g. "***"). For
    `PARTIAL` it can be the replacement character (defaults to "*").
    For `HASH` it is the salt; if empty, a process-stable random salt is
    generated at first use.
    """

    strategy: MaskingStrategy
    replacement: str = "*"
    salt: str = ""


@dataclass(frozen=True)
class RetentionPolicy:
    """Policy: this table is retained for this many days.

    `legal_hold` overrides the retention window — when true, no deletion
    is permitted regardless of age. `purpose` is a free-text reason
    that appears in deletion audit records.
    """

    retention_days: int
    legal_hold: bool = False
    purpose: Optional[str] = None
