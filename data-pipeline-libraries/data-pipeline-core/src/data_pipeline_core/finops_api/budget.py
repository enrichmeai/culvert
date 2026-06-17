"""Budget governance types — BudgetViolationMode, BudgetExceededException,
and BudgetGovernancePolicy.

Mirrors:
  - ``com.enrichmeai.culvert.finops.BudgetViolationMode``    (BudgetViolationMode.java)
  - ``com.enrichmeai.culvert.finops.BudgetExceededException`` (BudgetExceededException.java)
  - ``com.enrichmeai.culvert.finops.BudgetGovernancePolicy``  (BudgetGovernancePolicy.java)

Module placement follows the same rationale as the Java counterpart: this
code compares ``CostMetrics.estimated_cost_usd`` (a float) against a
configurable ceiling. It imports only stdlib + sibling core types —
zero cloud-SDK dependencies.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from data_pipeline_core.contracts.governance import GovernancePolicy
from data_pipeline_core.finops_api.models import CostMetrics
from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import MaskingPolicy, RetentionPolicy

logger = logging.getLogger(__name__)


class BudgetViolationMode(str, Enum):
    """Determines the action taken by :class:`BudgetGovernancePolicy` when a
    pipeline run's projected cost exceeds the configured ceiling.

    Mirrors ``BudgetViolationMode.java``.

    - ``BLOCK`` — raises :class:`BudgetExceededException`. Use in production
      or automated CI where runaway spend is unacceptable.
    - ``WARN``  — logs a ``WARNING`` via :mod:`logging` and allows the run to
      continue. Use in development or staging where visibility is more
      important than blocking.
    """

    BLOCK = "block"
    """Raise :class:`BudgetExceededException` when the projected cost exceeds
    the ceiling. The run does not proceed."""

    WARN = "warn"
    """Log a WARNING when the projected cost exceeds the ceiling. The run
    continues."""


class BudgetExceededException(Exception):
    """Raised by :class:`BudgetGovernancePolicy` when a pipeline run's
    projected cost exceeds the configured ceiling and the policy is in
    ``BLOCK`` mode.

    Mirrors ``BudgetExceededException.java``.

    The message is intentionally human-readable so that an error handler can
    surface it directly in a log or alert without additional formatting. It
    includes:

    - the pipeline ``run_id`` that triggered the check,
    - the ``projected_cost_usd`` reported by :class:`~data_pipeline_core.finops_api.models.CostMetrics`, and
    - the ``ceiling_usd`` that was exceeded.

    Callers that want structured access should use the typed properties.
    """

    def __init__(self, run_id: str, projected_cost_usd: float, ceiling_usd: float) -> None:
        super().__init__(
            f"Budget ceiling exceeded for run '{run_id}': "
            f"projected cost ${projected_cost_usd:.4f} USD > ceiling ${ceiling_usd:.4f} USD"
        )
        self._run_id = run_id
        self._projected_cost_usd = projected_cost_usd
        self._ceiling_usd = ceiling_usd

    @property
    def run_id(self) -> str:
        """The pipeline run identifier passed to :meth:`BudgetGovernancePolicy.check_budget`."""
        return self._run_id

    @property
    def projected_cost_usd(self) -> float:
        """The projected cost in USD (from ``CostMetrics.estimated_cost_usd``)."""
        return self._projected_cost_usd

    @property
    def ceiling_usd(self) -> float:
        """The cost ceiling in USD configured on the policy."""
        return self._ceiling_usd


class BudgetGovernancePolicy:
    """A :class:`~data_pipeline_core.contracts.governance.GovernancePolicy`
    implementation that enforces a cost ceiling on pipeline runs.

    Mirrors ``BudgetGovernancePolicy.java``.

    How it works
    ------------
    1. Before submitting a pipeline run, call
       :meth:`check_budget` with the estimate produced by
       ``BigQueryCostTracker.estimate_dry_run()`` (or equivalent).
    2. In ``BLOCK`` mode, the method raises :class:`BudgetExceededException`
       if ``projected.estimated_cost_usd > ceiling_usd``. The run does not
       proceed.
    3. In ``WARN`` mode, the method logs a ``WARNING`` via :mod:`logging` and
       returns normally. The run continues.

    GovernancePolicy inherited methods
    -----------------------------------
    The three methods inherited from
    :class:`~data_pipeline_core.contracts.governance.GovernancePolicy`
    (``classify``, ``masking_for``, ``retention_for``) provide no-op
    pass-through defaults: every field is
    :attr:`~data_pipeline_core.governance_api.classification.DataClassification.INTERNAL`,
    no masking applies, and no retention applies. These can be composed or
    overridden by wrapping this policy with a delegating implementation when
    full governance is also needed.

    No cloud-SDK imports
    --------------------
    This class intentionally imports only stdlib and sibling core types.
    """

    def __init__(self, ceiling_usd: float, mode: BudgetViolationMode) -> None:
        """Construct a new :class:`BudgetGovernancePolicy`.

        Parameters
        ----------
        ceiling_usd:
            The maximum allowed projected cost in USD (inclusive). A projected
            cost strictly greater than this value triggers the violation action.
        mode:
            The action to take on a violation: ``BLOCK`` raises, ``WARN`` logs
            and continues.

        Raises
        ------
        ValueError
            If ``ceiling_usd`` is negative.
        TypeError
            If ``mode`` is not a :class:`BudgetViolationMode`.
        """
        if ceiling_usd < 0.0:
            raise ValueError(f"ceiling_usd must be non-negative, got: {ceiling_usd}")
        if not isinstance(mode, BudgetViolationMode):
            raise TypeError(f"mode must be a BudgetViolationMode, got: {type(mode)!r}")
        self._ceiling_usd = ceiling_usd
        self._mode = mode

    @property
    def ceiling_usd(self) -> float:
        """The configured cost ceiling in USD."""
        return self._ceiling_usd

    @property
    def mode(self) -> BudgetViolationMode:
        """The configured violation mode."""
        return self._mode

    def check_budget(self, projected: CostMetrics, run_id: str) -> None:
        """Check whether the projected cost stays within the configured ceiling.

        If ``projected.estimated_cost_usd > ceiling_usd``:

        - ``BLOCK``: raises :class:`BudgetExceededException`.
        - ``WARN``: logs a ``WARNING`` and returns normally.

        If ``projected.estimated_cost_usd <= ceiling_usd``, this method always
        returns normally regardless of mode.

        Parameters
        ----------
        projected:
            The projected cost estimate (typically from
            ``BigQueryCostTracker.estimate_dry_run``).
        run_id:
            The pipeline run identifier, used in the exception message and
            log warning.

        Raises
        ------
        BudgetExceededException
            If in ``BLOCK`` mode and cost exceeds the ceiling.
        """
        if projected is None:
            raise TypeError("projected must not be None")
        if run_id is None:
            raise TypeError("run_id must not be None")

        estimated_cost = projected.estimated_cost_usd
        if estimated_cost <= self._ceiling_usd:
            return  # within budget — no action needed

        # Cost exceeds ceiling — take the configured action.
        if self._mode is BudgetViolationMode.BLOCK:
            raise BudgetExceededException(run_id, estimated_cost, self._ceiling_usd)
        else:
            # WARN mode: log and continue
            logger.warning(
                "Budget ceiling exceeded for run '%s': projected cost $%.4f USD > "
                "ceiling $%.4f USD — run will proceed (WARN mode)",
                run_id,
                estimated_cost,
                self._ceiling_usd,
            )

    # -------------------------------------------------------------------------
    # GovernancePolicy pass-through methods (no-op defaults)
    #
    # This policy's concern is cost enforcement. The three GovernancePolicy
    # methods below provide inert defaults so BudgetGovernancePolicy can be
    # used wherever a GovernancePolicy is expected without mixing
    # masking/retention concerns into this class.
    # -------------------------------------------------------------------------

    def classify(self, field: str, table: str) -> DataClassification:
        """Return :attr:`~data_pipeline_core.governance_api.classification.DataClassification.INTERNAL`
        for every field/table. No data-catalog lookup is performed.
        """
        return DataClassification.INTERNAL

    def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]:
        """Return ``None`` — no masking policy is enforced by this
        cost-governance implementation.
        """
        return None

    def retention_for(self, table: str) -> Optional[RetentionPolicy]:
        """Return ``None`` — no retention policy is enforced by this
        cost-governance implementation.
        """
        return None
