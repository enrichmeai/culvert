"""AuditEvent - one row of ``job_control.audit_events`` (docs/CONTRACT.md section 4).

Replaces ``AuditRecord``, which modelled a *stage summary* (eleven fields:
durations, success flags, hashes) while the contract specifies an *event*. The
two shared exactly one column, ``run_id``, so this is a different unit of
emission rather than a field rename - which is why there is no adapter between
them.

Python mirror of the Java ``com.enrichmeai.culvert.audit.AuditEvent`` record.
Both languages are asserted against the SAME fixtures at
``tests/contract/fixtures/audit_events.json``, so they cannot drift on column
names, event kinds, or payload keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional

CONTRACT_VERSION = "1.0.0"
"""The single source of the ``contract_version`` every emitted record carries.

One constant, stamped by :class:`AuditEvent` - never duplicated per adapter and
never passed in by a caller. Both alternatives fail the same way: an adapter
drifts to a stale value, or forgets the field and the row claims conformance to
nothing.

docs/CONTRACT.md section 2 is explicit that producers MUST NOT increment this
unilaterally; it is bumped by a PR to that document and its fixtures.
"""


class EventKind(Enum):
    """The kinds of event an audit log carries - section 4's enum, verbatim.

    Each kind decides two things: what happens when its append fails
    (:meth:`is_run_level`), and what its payload must contain
    (:attr:`required_payload_keys`).
    """

    RUN_START = ("RUN_START", True, ("source_file",))
    RUN_END = ("RUN_END", True, ("record_count",))
    RECORD_VALIDATED = ("RECORD_VALIDATED", False, ("count",))
    RECORD_REJECTED = ("RECORD_REJECTED", False, ("count", "quarantine_uri"))
    RECONCILIATION = (
        "RECONCILIATION", True, ("expected_count", "accounted_count", "reconciled"),
    )
    ERROR_RAISED = ("ERROR_RAISED", True, ("error_code", "error_category"))
    RETRY_ATTEMPTED = ("RETRY_ATTEMPTED", True, ("attempt", "previous_run_id"))

    def __init__(self, wire: str, run_level: bool, required: tuple) -> None:
        self._wire = wire
        self._run_level = run_level
        self._required = required

    @property
    def wire_value(self) -> str:
        """The value written to ``event_kind``. Uppercase, per section 4."""
        return self._wire

    def is_run_level(self) -> bool:
        """True if this event carries the run's state rather than a counter.

        A failed append of a run-level event THROWS and fails the pipeline:
        proceeding without it is how a run reports success it never had. A
        failed aggregate append logs at ERROR and dead-letters, so an audit
        hiccup over a counter cannot halt ingestion. Either way **nothing is
        swallowed**.
        """
        return self._run_level

    @property
    def required_payload_keys(self) -> tuple:
        """Payload keys this kind must carry.

        Section 10.3 forbids extra columns on a well-known table, so everything
        past section 4's ten columns lives in ``payload`` - the largest
        divergence surface in this design if left unbound.
        """
        return self._required

    @classmethod
    def from_wire(cls, value: str) -> "EventKind":
        """Parse a wire value, rejecting anything section 4 does not define."""
        for kind in cls:
            if kind.wire_value == value:
                return kind
        valid = ", ".join(k.wire_value for k in cls)
        raise ValueError(
            f"Unknown event_kind {value!r}; docs/CONTRACT.md section 4 defines: {valid}"
        )


@dataclass(frozen=True)
class AuditEvent:
    """One row of ``job_control.audit_events``.

    ``contract_version`` is stamped by this type, and the payload keys required
    by the event kind are checked at construction - so a missing key fails
    HERE, loudly, rather than reading back as NULL from a JSON path months
    later in a query nobody thinks to distrust.
    """

    run_id: str
    system_id: str
    entity: str
    event_kind: EventKind
    event_ts: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)
    extract_date: Optional[date] = None
    producer: Optional[str] = None
    environment: Optional[str] = None
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must not be blank")
        if not self.entity:
            raise ValueError("entity must not be blank")
        if not isinstance(self.event_kind, EventKind):
            raise TypeError(f"event_kind must be an EventKind, got {type(self.event_kind)}")

        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

        missing = [
            k for k in self.event_kind.required_payload_keys if k not in self.payload
        ]
        if missing:
            raise ValueError(
                f"{self.event_kind.wire_value} requires payload key(s) {missing}; got "
                f"{sorted(self.payload)}. See docs/CONTRACT.md section 4."
            )

    def failure_is_fatal(self) -> bool:
        """True if a failed append of this event must fail the pipeline.

        Delegates to the kind so the rule lives in one place - restating it per
        emitter is how two emitters end up disagreeing about which failures
        matter.
        """
        return self.event_kind.is_run_level()
