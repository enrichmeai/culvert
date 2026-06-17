"""PiiMaskingGovernancePolicy — structural GovernancePolicy implementation.

Identifies PII fields by column-name membership and/or regex pattern
matching, then applies a configured MaskingPolicy.

Mirrors Java ``com.enrichmeai.culvert.governance.PiiMaskingGovernancePolicy``
(Sprint 14 / T14.4 / issue #76).

Matching rules (applied in order; first match wins)
----------------------------------------------------
1. **Column-name set** — exact, case-sensitive comparison against the
   ``pii_columns`` set supplied at construction.
   E.g. ``{"email", "ssn", "phone"}``.
2. **Regex patterns** — each pattern in ``pii_patterns`` is tested with
   ``re.fullmatch()`` (anchored full-field-name match, mirroring Java
   ``Matcher.matches()``).  E.g. ``[".*_pii$", ".*_secret$"]``.

Classification
--------------
A field that matches either rule → ``DataClassification.RESTRICTED``.
All other fields → ``DataClassification.INTERNAL``.

Masking policy resolution
--------------------------
When a field matches:
1. If ``column_overrides`` contains an entry for that field name, that
   MaskingPolicy is used.
2. Otherwise ``default_masking_policy`` is used.

``column_overrides`` only overrides the *policy* for already-matched
fields. A key present only in the override map (not in the column set
and not matching any pattern) does NOT by itself make a field match.

Scope cap
---------
Structural only — inspects field names, not values. Tag-based policy
resolution (Dataplex, Cloud DLP, Purview) is out of scope. Do not add
cloud SDK imports here.
"""

from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence

from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import MaskingPolicy, RetentionPolicy


class PiiMaskingGovernancePolicy:
    """A structural :class:`GovernancePolicy` for PII masking.

    Parameters
    ----------
    pii_columns:
        Exact column names that are PII (case-sensitive).  May be empty.
    pii_patterns:
        Regex pattern strings tested against field names via
        ``re.fullmatch()`` (anchored, mirrors Java ``Matcher.matches()``).
        May be empty.  Patterns are compiled once at construction time.
    default_masking_policy:
        Applied when a field matches and no per-column override exists.
        Required.
    column_overrides:
        Optional per-column policy overrides, applied only to *matched*
        fields.

    Raises
    ------
    ValueError
        If ``default_masking_policy`` is ``None``.
    re.error
        If any pattern in ``pii_patterns`` is invalid.
    """

    # Mirrors Java PiiMaskingGovernancePolicy (PiiMaskingGovernancePolicy.java:73)

    def __init__(
        self,
        pii_columns: Optional[FrozenSet[str] | frozenset | set] = None,
        pii_patterns: Optional[Sequence[str]] = None,
        default_masking_policy: Optional[MaskingPolicy] = None,
        column_overrides: Optional[Mapping[str, MaskingPolicy]] = None,
    ) -> None:
        if default_masking_policy is None:
            raise ValueError("default_masking_policy must not be None")

        self._pii_columns: FrozenSet[str] = frozenset(pii_columns) if pii_columns else frozenset()
        self._compiled_patterns: List[re.Pattern[str]] = [
            re.compile(p) for p in (pii_patterns or [])
        ]
        self._default_masking_policy: MaskingPolicy = default_masking_policy
        self._column_overrides: Dict[str, MaskingPolicy] = dict(column_overrides) if column_overrides else {}

    # ------------------------------------------------------------------
    # GovernancePolicy implementation
    # ------------------------------------------------------------------

    def classify(self, field: str, table: str) -> DataClassification:
        """Return RESTRICTED if *field* is PII, INTERNAL otherwise.

        Mirrors Java ``PiiMaskingGovernancePolicy.classify``
        (PiiMaskingGovernancePolicy.java:137-139).
        """
        return DataClassification.RESTRICTED if self._is_pii(field) else DataClassification.INTERNAL

    def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]:
        """Return the masking policy for *field*, or None if not PII.

        Column override (if present) takes precedence over the default.

        Mirrors Java ``PiiMaskingGovernancePolicy.maskingFor``
        (PiiMaskingGovernancePolicy.java:152-157).
        """
        if not self._is_pii(field):
            return None
        return self._column_overrides.get(field, self._default_masking_policy)

    def retention_for(self, table: str) -> Optional[RetentionPolicy]:
        """Always returns None — this policy does not manage retention.

        Mirrors Java ``PiiMaskingGovernancePolicy.retentionFor``
        (PiiMaskingGovernancePolicy.java:163-165).
        """
        return None

    # ------------------------------------------------------------------
    # Accessors (for tests and composition)
    # ------------------------------------------------------------------

    @property
    def pii_columns(self) -> FrozenSet[str]:
        """Unmodifiable view of the explicit PII column-name set."""
        return self._pii_columns

    @property
    def default_masking_policy(self) -> MaskingPolicy:
        """The default masking policy."""
        return self._default_masking_policy

    @property
    def column_overrides(self) -> Dict[str, MaskingPolicy]:
        """Unmodifiable copy of the per-column override map."""
        return dict(self._column_overrides)

    # ------------------------------------------------------------------
    # Internal: shared match predicate
    # ------------------------------------------------------------------

    def _is_pii(self, field_name: str) -> bool:
        """Return True iff *field_name* is in the column set or matches a regex.

        Single source of truth for both :meth:`classify` and
        :meth:`masking_for` — mirrors Java ``PiiMaskingGovernancePolicy.isPii``
        (PiiMaskingGovernancePolicy.java:197-202).

        Uses ``re.fullmatch`` to mirror Java ``Matcher.matches()``
        (anchored full-string match).
        """
        if field_name in self._pii_columns:
            return True
        for pattern in self._compiled_patterns:
            if pattern.fullmatch(field_name):
                return True
        return False


# ---------------------------------------------------------------------------
# Runtime_checkable assertion (documented, not enforced here)
# ---------------------------------------------------------------------------
# PiiMaskingGovernancePolicy satisfies GovernancePolicy by structural typing
# (duck typing / Protocol). No explicit inheritance is required.
# Verified by: isinstance(PiiMaskingGovernancePolicy(...), GovernancePolicy)
