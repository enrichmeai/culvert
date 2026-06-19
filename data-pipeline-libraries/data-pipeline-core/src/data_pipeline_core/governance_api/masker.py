"""Masker — applies a MaskingPolicy to a single field value.

Cloud-neutral utility: no GCP SDK, Cloud DLP, Dataplex, or external
imports. All masking is structural — based on field-name matching, not
per-cell content inspection.

Mirrors Java ``com.enrichmeai.culvert.governance.Masker`` (Sprint 14 / T14.4).

Supported strategies
--------------------
NONE      — value returned unchanged.
FULL      — value replaced with policy.replacement (default "*").
REDACTED  — same as FULL; value replaced with policy.replacement.
PARTIAL   — all characters replaced with policy.replacement[0] (or '*')
            except the last 4, which are kept. If the value has 4 or
            fewer characters, all characters are replaced.  Non-string
            values are converted via str() first.
HASH      — deterministic SHA-256 hex digest of (salt + value).  If
            policy.salt is empty, the constant process-stable salt
            ``"culvert-pii-salt"`` is used (mirrors Java DEFAULT_SALT).

Null passthrough
----------------
If ``value`` is ``None`` the method returns ``None`` regardless of strategy
— nulls are not fabricated.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from data_pipeline_core.governance_api.policies import MaskingPolicy, MaskingStrategy

# Mirrors Java ``Masker.DEFAULT_SALT`` (Masker.java:41)
_DEFAULT_SALT = "culvert-pii-salt"


def mask(value: Optional[Any], policy: MaskingPolicy) -> Optional[Any]:
    """Apply *policy* to *value* and return the masked result.

    Parameters
    ----------
    value:
        The field value to mask.  ``None`` is returned unchanged.
    policy:
        The masking policy.  Must not be ``None``.

    Returns
    -------
    The masked value, or ``None`` if *value* was ``None``.

    Raises
    ------
    TypeError
        If *policy* is ``None``.
    """
    if policy is None:
        raise TypeError("policy must not be None")
    if value is None:
        return None

    strategy = policy.strategy

    if strategy is MaskingStrategy.NONE:
        return value
    if strategy in (MaskingStrategy.FULL, MaskingStrategy.REDACTED):
        return policy.replacement
    if strategy is MaskingStrategy.PARTIAL:
        return _mask_partial(str(value), policy.replacement)
    if strategy is MaskingStrategy.HASH:
        return _mask_hash(str(value), policy.salt)

    # Unreachable for a well-formed MaskingStrategy enum, but guard anyway.
    raise ValueError(f"Unsupported MaskingStrategy: {strategy!r}")  # pragma: no cover


# ---------------------------------------------------------------------------
# Strategy helpers — mirrors Java private methods in Masker.java
# ---------------------------------------------------------------------------

def _mask_partial(s: str, replacement: str) -> str:
    """Mask all characters except the last 4.

    Mirrors Java ``Masker.maskPartial`` (Masker.java:74-81).
    """
    repl_char = replacement[0] if replacement else "*"
    if len(s) <= 4:
        return repl_char * len(s)
    suffix = s[-4:]
    return repl_char * (len(s) - 4) + suffix


def _mask_hash(value: str, salt: str) -> str:
    """Return a deterministic SHA-256 hex digest of (effective_salt + value).

    Mirrors Java ``Masker.maskHash`` (Masker.java:87-101): salt is prepended
    to value before hashing.
    """
    effective_salt = salt if salt else _DEFAULT_SALT
    digest = hashlib.sha256((effective_salt + value).encode("utf-8")).hexdigest()
    return digest
